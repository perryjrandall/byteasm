from . assemble import *
from . constants import *
from . utils import *

from inspect import Parameter, Signature

import itertools
import opcode

__all__ = [ 
    'EmittersMixin'
  , 'FunctionBuilder'
  ]

##################################################
#                                                #
##################################################
UnknownFilename   = '?????'

##################################################
#                                                #
##################################################
def _make_nullary_emitter( code, fop ) :
  def emit( self ) :
    return self._insert_op( code, NilArg, None, fop )
  return emit

def _make_unary_emitter_cmp( code, fop ) :
  def emit( self, op ) :
    if not isinstance(op,int) :
      op = opcode.cmp_op.index( op )
    return self._insert_op( code, GenericArg, op, fop )
  return emit

def _make_unary_emitter_const( code, fop ) :
  def emit( self, value ) :
    return self._insert_op( code, ConstantArg, value, fop )
  return emit

def _make_unary_emitter_free( code, fop ) :
  def emit( self, name ) :
    return self._insert_op( code, FreeVariableArg, name, fop )
  return emit

def _make_unary_emitter_generic( code, fop ) :
  def emit( self, value ) :
    return self._insert_op( code, GenericArg, value, fop )
  return emit

def _make_unary_emitter_abslab( code, fop ) :
  def emit( self, label ) :
    return self._insert_op( code, AbsLabelArg, label, fop )
  return emit

def _make_unary_emitter_rellab( code, fop ) :
  def emit( self, label ) :
    return self._insert_op( code, RelLabelArg, label, fop )
  return emit

def _make_unary_emitter_local( code, fop ) :
  def emit( self, name ) :
    return self._insert_op( code, LocalArg, name, fop )
  return emit

def _make_unary_emitter_name( code, fop ) :
  def emit( self, name ) :
    return self._insert_op( code, NameArg, name, fop )
  return emit

def _add_emitter( cls, name, code ) :

  if code < opcode.HAVE_ARGUMENT :
    ctor = _make_nullary_emitter
  elif code in opcode.hascompare :
    ctor = _make_unary_emitter_cmp
  elif code in opcode.hasconst :
    ctor = _make_unary_emitter_const
  elif code in opcode.hasfree :
    ctor = _make_unary_emitter_free
  elif code in opcode.hasjabs :
    ctor = _make_unary_emitter_abslab
  elif code in opcode.hasjrel :
    ctor = _make_unary_emitter_rellab
  elif code in opcode.haslocal :
    ctor = _make_unary_emitter_local
  elif code in opcode.hasname :
    ctor = _make_unary_emitter_name
  else :
    ctor = _make_unary_emitter_generic

  emitter = ctor( code, fop(code) )

  emitter.__name__      = 'emit_' + name.lower()
  emitter.__qualname__  = 'EmittersMixin.' + emitter.__name__
  emitter.__doc__       = f'Emits an opcode of type {name} into the instruction stream.'

  setattr( cls, emitter.__name__, emitter )


##
class EmittersMixin( object ) :

  def emit_compare_lt( self ) :
    return self.emit_compare_op( COMPARE_LT )

  def emit_compare_le( self ) :
    return self.emit_compare_op( COMPARE_LE )

  def emit_compare_eq( self ) :
    return self.emit_compare_op( COMPARE_EQ )

  def emit_compare_ne( self ) :
    return self.emit_compare_op( COMPARE_NE )

  def emit_compare_ge( self ) :
    return self.emit_compare_op( COMPARE_GE )

  def emit_compare_gt( self ) :
    return self.emit_compare_op( COMPARE_GT )

  def emit_compare_is( self ) :
    return self.emit_compare_op( COMPARE_IS )

  def emit_compare_is_not( self ) :
    return self.emit_compare_op( COMPARE_IS_NOT )

  def emit_compare_in( self ) :
    return self.emit_compare_op( COMPARE_IN )

  def emit_compare_not_in( self ) :
    return self.emit_compare_op( COMPARE_NOT_IN )
    
  def emit_compare_exception( self ) :
    return self.emit_compare_op( COMPARE_EXCEPTION )

  def emit_label( self, label=None ) :
    return self._emit_label( label )

##
for name,code in opcode.opmap.items() :
  _add_emitter(EmittersMixin,name,code)

##################################################
#                                                #
##################################################
class FunctionBuilder( EmittersMixin ) :

  def __init__( self, first_line_number=1 ) :
    self._positional     = []
    self._keyword_only   = []
    self._agg_positional = []
    self._agg_keyword    = []
    self._op_buffer      = []
    self._labels         = {}
    self._label_seq      = itertools.count(1)
    self._closure        = {}
    self._line_number    = first_line_number

  def __len__( self ) :
    return len(self._op_buffer)

  def add_positional_arg( self, name, **kwargs ) :
    self._positional.append( Parameter( name, Parameter.POSITIONAL_OR_KEYWORD, **kwargs ) )

  def add_keyword_only_arg( self, name, **kwargs ) :
    self._keyword_only.append( Parameter( name, Parameter.KEYWORD_ONLY, **kwargs ) )

  def add_agg_positional_arg( self, name, **kwargs ) :
    self._agg_positional.append( Parameter( name, Parameter.VAR_POSITIONAL, **kwargs ) )

  def add_agg_keyword_arg( self, name, **kwargs ) :
    self._agg_keyword.append( Parameter( name, Parameter.VAR_KEYWORD, **kwargs ) )

  def set_closure_value( self, key, value ) :
    self._closure[ key ] = value

  def make_label( self, head='auto' ) :
    idx = next(self._label_seq)
    return f'{head}_{idx}'

  def inc_line_number( self, delta=1 ) :
    self._line_number += delta

  def set_line_number( self, value ) :
    self._line_number = value

  def _insert_op( self, *args ) :
    self._op_buffer.append( (self._line_number,*args) )

  def _emit_label( self, label ) :
    if label is None :
      label = self.make_label()
    self._labels[ label ] = len(self._op_buffer)
    return label

  def make( 
          self
        , name
        , fglobals          = None
        , *
        , signature         = None
        , docstring         = None
        , stackdepth        = None
        , filename          = UnknownFilename
        ) :

    if signature is None :
      signature = Signature( 
                      self._positional
                    + self._keyword_only
                    + self._agg_positional
                    + self._agg_keyword
                    )

    return assemble(      
                name              = name
              , fglobals          = fglobals
              , signature         = signature
              , docstring         = docstring
              , stackdepth        = stackdepth
              , filename          = filename
              , ops               = self._op_buffer
              , labels            = self._labels
              , closure_values    = self._closure
              )


