from . constants import *
from . stack import *
from . utils import *

from ctypes import c_uint16, c_int16
from inspect import currentframe, Parameter, Signature

import collections
import itertools
import opcode
import types

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
_visualization_hook = PASS

##################################################
#                                                #
##################################################
def _set_generator_flag( flags ) :
  return flags|CO_GENERATOR

def _unset_optimized_flag( flags ) :
  return flags&~CO_OPTIMIZED

def _make_nullary_emitter( code, fop ) :
  def emit( self ) :
    return self._assembler.insert_op( (code,None,NilArg), 1, fop )
  return emit

def _make_unary_emitter_cmp( code, fop ) :
  def emit( self, op ) :
    if not isinstance(op,int) :
      op = opcode.cmp_op.index( op )
    return self._assembler.insert_op( (code,op,GenericArg), 3, fop )
  return emit

def _make_unary_emitter_const( code, fop ) :
  def emit( self, value ) :
    return self._assembler.insert_op( (code,value,ConstantArg), 3, fop )
  return emit

def _make_unary_emitter_free( code, fop ) :
  def emit( self, name ) :
    return self._assembler.insert_op( (code,name,FreeVariableArg), 3, fop )
  return emit

def _make_unary_emitter_generic( code, fop ) :
  def emit( self, value ) :
    return self._assembler.insert_op( (code,value,GenericArg), (3 if value <= 0xFFFF else 6), fop )
  return emit

def _make_unary_emitter_abslab( code, fop ) :
  def emit( self, label ) :
    # assumes that we can reach everything with a 16-bit
    # delta. this assumption may have to be fixed up later
    return self._assembler.insert_op( (code,label,AbsLabelArg), 3, fop )
  return emit

def _make_unary_emitter_rellab( code, fop ) :
  def emit( self, label ) :
    # assumes that we can reach everything with a 16-bit
    # delta. this assumption may have to be fixed up later
    return self._assembler.insert_op( (code,label,RelLabelArg), 3, fop )
  return emit

def _make_unary_emitter_local( code, fop ) :
  def emit( self, name ) :
    return self._assembler.insert_op( (code,name,LocalArg), 3, fop )
  return emit

def _make_unary_emitter_name( code, fop ) :
  def emit( self, name ) :
    return self._assembler.insert_op( (code,name,NameArg), 3, fop )
  return emit

def _add_emitter( cls, name, code ) :

  fop = None
  if code == YIELD_VALUE :
    fop = _set_generator_flag
  elif code in ( DELETE_NAME, LOAD_NAME, STORE_NAME ) :
    fop = _unset_optimized_flag

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

  emitter = ctor( code, fop )

  emitter.__name__      = 'emit_' + name.lower()
  emitter.__qualname__  = 'EmittersMixin.' + emitter.__name__
  emitter.__doc__       = str.format( 'Emits an opcode of type {} into the instruction stream.', name )

  setattr( cls, emitter.__name__, emitter )


##
class EmittersMixin( object ) :

  def make_label( self, *args, **kwargs ) :
    return self._assembler.make_label( *args, **kwargs )

  def emit_label( self, *args, **kwargs ) :
    return self._assembler.insert_label( *args, **kwargs )

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
    

##
for name,code in opcode.opmap.items() :
  _add_emitter(EmittersMixin,name,code)


##################################################
#                                                #
##################################################
class InternArray( collections.OrderedDict ) :

  def __init__( self, initial=() ) :
    super().__init__( (e,i) for (i,e) in enumerate(initial) )

  def insert( self, key ) :
    return self.setdefault( key, len(self) )

  def as_tuple( self ) :
    return tuple( self.keys() )


##################################################
#                                                #
##################################################
class ByteCodeAssembler( object ) :

  def __init__( self ) :
    self._buffer    = []
    self._labels    = {}
    self._ip        = 0
    self._flags     = CO_OPTIMIZED
    self._label_seq = itertools.count(1)

  def __len__( self ) :
    return self._ip

  def make_label( self, head='auto' ) :
    return str.format( '{}_{}', head, next(self._label_seq) )

  def insert_label( self, label=None ) :
    if label is None :
      label = self.make_label()
    self._labels[ label ] = self._ip
    return label

  def insert_op( self, desc, oplen, fop ) :
    self._ip += oplen
    self._buffer.append( desc )
    if fop is not None :
      self._flags = fop( self._flags )

  def finalize( 
          self
        , name
        , *
        , arglist            = ()
        , positional_count   = 0
        , kwonly_count       = 0
        , has_agg_positional = False
        , has_agg_keyword    = False
        , stackdepth         = None
        , filename           = UnknownFilename
        , first_line_number  = 1
        ) :

    code       = bytearray()
    lineno_tab = bytearray()

    cellvars   = InternArray()
    constants  = InternArray()
    freevars   = InternArray()
    names      = InternArray()
    varnames   = InternArray( arglist )
    tabs       = (constants,freevars,names,varnames)

    se_ins = PASS
    if stackdepth is None :
      se = StackEffects( self._labels )
      se_ins = se.insert

    for op, raw, typ in self._buffer :

      if typ >= ConstantArg :

        arg = tabs[typ-ConstantArg].insert( raw )

      elif typ >= AbsLabelArg :

        raw = self._labels[raw]

        arg = raw
        if typ == RelLabelArg :
          arg -= len(code) + 3

        if c_int16(arg).value != arg :
          raise AssertionError( 'fixup required' )

      else :
        
        arg = raw

      if arg is None :
        code.append( op )

      elif arg <= 0xFFFF :
        code.append( op )
        code.extend( c_uint16(arg) )

      else :
        code.append( EXTENDED_ARG )
        code.extend( c_uint16(arg>>16) )
        code.append( op )
        code.extend( c_uint16(arg) )

      se_ins( len(code), op, raw, arg, typ )

    _visualization_hook( name, se )

    max_stack = compute_stack_depth( se ) \
                  if stackdepth is None   \
                  else stackdepth

    if len(code) != self._ip :
      raise AssertionError( 'generated code has unexpected length' )

    flags = self._flags
    if has_agg_positional :
      flags |= CO_VARARGS 
    if has_agg_keyword :
      flags |= CO_VARKEYWORDS
    if varnames :
      flags |= CO_NEWLOCALS
    if not freevars :
      flags |= CO_NOFREE

    return types.CodeType(
                  positional_count
                , kwonly_count
                , len(varnames)
                , max_stack
                , flags
                , bytes(code)
                , constants.as_tuple()
                , names.as_tuple()
                , varnames.as_tuple()
                , filename
                , name
                , first_line_number
                , bytes(lineno_tab)
                , freevars.as_tuple()
                , cellvars.as_tuple()
                )



##################################################
#                                                #
##################################################
class SignatureBuilder( object ) :

  def __init__( self ) :
    self._positional     = []
    self._keyword_only   = []
    self._agg_positional = []
    self._agg_keyword    = []

  def add_positional( self, name, **kwargs ) :
    self._positional.append( Parameter( name, Parameter.POSITIONAL_OR_KEYWORD, **kwargs ) )

  def add_keyword_only( self, name, **kwargs ) :
    self._keyword_only.append( Parameter( name, Parameter.KEYWORD_ONLY, **kwargs ) )

  def add_agg_positional( self, name, **kwargs ) :
    self._agg_positional.append( Parameter( name, Parameter.VAR_POSITIONAL, **kwargs ) )

  def add_agg_keyword( self, name, **kwargs ) :
    self._agg_keyword.append( Parameter( name, Parameter.VAR_KEYWORD, **kwargs ) )

  def make( self ) :
    return Signature( 
                self._positional
              + self._keyword_only
              + self._agg_positional
              + self._agg_keyword
              )


##################################################
#                                                #
##################################################
class FunctionBuilder( EmittersMixin ) :

  def __init__( self ) :
    self._sigbuilder = SignatureBuilder()
    self._assembler  = ByteCodeAssembler()
    self._closure    = {}

  def __len__( self ) :
    return len(self._assembler)

  def add_positional_arg( self, *args, **kwargs ) :
    self._sigbuilder.add_positional( *args, **kwargs )

  def add_keyword_only_arg( self, *args, **kwargs ) :
    self._sigbuilder.add_keyword_only( *args, **kwargs )

  def add_agg_positional_arg( self, *args, **kwargs ) :
    self._sigbuilder.add_agg_positional( *args, **kwargs )

  def add_agg_keyword_arg( self, *args, **kwargs ) :
    self._sigbuilder.add_agg_keyword( *args, **kwargs )

  def set_closure_value( self, key, value ) :
    # python requires `__closure__` values to be of the
    # `cell`, but doesn't give us a python API with which to
    # create them. to get one, we create a pure-python
    # function through the normal route and steal a
    # copy of the cell variable from the result
    self._closure[ key ] = (lambda : value).__closure__[0]

  def make( 
          self
        , name
        , fglobals          = None
        , *
        , signature         = None
        , docstring         = None
        , stackdepth        = None
        , filename          = UnknownFilename
        , first_line_number = 1
        ) :

    if signature is None :
      signature = self._sigbuilder.make()

    arglist             = []
    positional_defaults = []
    keyword_defaults    = {}
    positional_count    = 0
    kwonly_count        = 0
    has_agg_positional  = False
    has_agg_keyword     = False

    for k,p in signature.parameters.items() :

      arglist.append(p.name)

      if p.kind == p.VAR_KEYWORD :
        has_agg_keyword = True
      elif p.kind == p.VAR_POSITIONAL :
        has_agg_positional = True
      elif p.kind == p.KEYWORD_ONLY :
        kwonly_count += 1
        if p.default is not p.empty :
          keyword_defaults[p.name] = p.default
      else :
        if p.default is not p.empty :
          positional_defaults.append( p.default )
        positional_count += 1

    co = self._assembler.finalize(
                name               = name
              , arglist            = arglist
              , positional_count   = positional_count
              , kwonly_count       = kwonly_count
              , has_agg_positional = has_agg_positional
              , has_agg_keyword    = has_agg_keyword
              , filename           = filename
              , first_line_number  = first_line_number
              , stackdepth         = stackdepth
              )

    if fglobals is None :
      fglobals = currentframe().f_back.f_globals

    fn = types.FunctionType( 
                co
              , fglobals
              , name
              , tuple(positional_defaults) or None
              , tuple_map( self._closure.__getitem__, co.co_freevars ) or None
              )

    if keyword_defaults :
      fn.__kwdefaults__ = keyword_defaults

    return fn


  
