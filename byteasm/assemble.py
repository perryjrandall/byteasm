from . constants import *
from . stack import *
from . utils import *

import collections
import inspect
import types

__all__ = [
    'assemble'
  , 'fop'
  ]

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

def fop( code ) :

  if code == YIELD_VALUE :
    return _set_generator_flag

  if code in ( DELETE_NAME, LOAD_NAME, STORE_NAME ) :
    return _unset_optimized_flag


##################################################
#                                                #
##################################################
def _make_closure( value ) :
  # python requires `__closure__` values to be of the
  # `cell`, but doesn't give us a python API with which to
  # create them. To get one, we create a pure-python
  # function through the normal route and steal a
  # copy of the cell variable from the result
  return (lambda : value).__closure__[0]


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


##
class LineNumbering( object ) :

  def __init__( self, first_line ) :
    self._first_line = first_line
    self._last_line  = first_line
    self._last_ip    = 0
    self._tab        = bytearray()

  def first( self ) :
    return self._first_line
  
  def bytes( self ) :
    return bytes( self._tab )

  def add( self, line, ip ) :

    if line > self._last_line :

      while True :
        delta_ip   = ip - self._last_ip
        delta_line = min(line - self._last_line,0x7F)
        self._tab.append( delta_ip )
        self._tab.append( delta_line )
        self._last_ip += delta_ip
        self._last_line += delta_line
        if line == self._last_line :
          break

    elif line < self._last_line :

      while True :
        delta_ip   = ip - self._last_ip
        delta_line = min(self._last_line-line,0x80)
        self._tab.append( delta_ip )
        self._tab.append( 0x100-delta_line )
        self._last_ip += delta_ip
        self._last_line -= delta_line
        if line == self._last_line :
          break

    elif ip - self._last_ip > 0xFF :

      while True :
        self._tab.append( 0xFF )
        self._tab.append( 0 )
        self._last_ip += 0xFF
        if ip - self._last_ip <= 0xFF :
          break




##################################################
#                                                #
##################################################
def assemble( 
        name
      , fglobals
      , signature
      , docstring
      , stackdepth
      , filename
      , ops
      , labels
      , closure_values
      ) :

  flags     = CO_OPTIMIZED
  cellvars  = InternArray()
  constants = InternArray()
  freevars  = InternArray()
  names     = InternArray()
  varnames  = InternArray()

  # decompose signature
  arglist             = []
  positional_defaults = []
  keyword_defaults    = {}
  positional_count    = 0
  kwonly_count        = 0

  for k,p in signature.parameters.items() :

    varnames.insert( p.name )

    if p.kind == p.VAR_KEYWORD :
      flags |= CO_VARKEYWORDS
    elif p.kind == p.VAR_POSITIONAL :
      flags |= CO_VARARGS 
    elif p.kind == p.KEYWORD_ONLY :
      kwonly_count += 1
      if p.default is not p.empty :
        keyword_defaults[p.name] = p.default
    else :
      if p.default is not p.empty :
        positional_defaults.append( p.default )
      positional_count += 1

  # encode op args. Assumes instructions are at most 4 bytes.
  # backward jumps are resolved here, but forward jumps are not
  ip = 0
  encoded = []
  for idx, (line, op, typ, raw, fop) in enumerate(ops) :

    oplen = 2
    arg = None

    if typ == GenericArg :
      arg = raw

    elif typ == AbsLabelArg :
      raw = labels[raw]
      if raw < idx :
        # for backwards jumps use the actual byte offset
        # as our argument
        arg = encoded[raw][-1]
      else :
        # for forward jumps, make the pessimistic assumption
        # that all instructions that we have not yet encoded
        # are 4 bytes
        oplen += 2*(ip+(raw-idx)*4 > 0xFF)

    elif typ == RelLabelArg :

      raw = labels[raw]

      # make the pessimistic assumption that all instructions 
      # that we have not yet encoded are 4 bytes
      oplen += 2*(raw-idx>=0x41)

    elif typ == ConstantArg :
      arg = constants.insert(raw)

    elif typ == FreeVariableArg :
      arg = freevars.insert(raw)

    elif typ == NameArg :
      arg = names.insert(raw)

    elif typ == LocalArg :
      arg = varnames.insert(raw)

    if arg is not None :
      value = arg
      while value > 0xFF :
        value >>= 8
        oplen += 2

    encoded.append((line,op,typ,raw,arg,oplen,ip))
    ip += oplen
    if fop is not None :
      flags = fop(flags)

  expected_length = ip
  if varnames :
    flags |= CO_NEWLOCALS
  if not freevars :
    flags |= CO_NOFREE

  # generate bytes and compute stack depth
  code = bytearray()

  se_ins = PASS
  if stackdepth is None :
    se = StackEffects({ k:encoded[v][-1] for (k,v) in labels.items() })
    se_ins = se.insert

  lntab = LineNumbering( encoded[0][0] )
  for line, op, typ, raw, arg, oplen, ip in encoded :

    # resolve forward jumps and convert jump targets
    # from an instruction number to an actual byte offset
    if typ == AbsLabelArg :
      abs = encoded[raw][-1]
      arg = abs

    elif typ == RelLabelArg :
      abs = encoded[raw][-1]
      arg = abs - ip - 1
    
    else :
      abs = raw

    # write actual opcodes to buffer
    eff_arg = arg or 0
    if oplen == 4 :
      code.append( EXTENDED_ARG )
      code.append( eff_arg>>8 )
      code.append( op )
      code.append( eff_arg&0xFF )
    elif oplen == 2 :
      code.append( op )
      code.append( eff_arg )
    else :
      raise AssertionError( 'invalid oplen' )

    # line numbering
    lntab.add( line, ip )

    # stack effects
    se_ins( ip, oplen, op, abs, arg, typ )

  if stackdepth is None :
    _visualization_hook( name, se )
    stackdepth = compute_stack_depth( se )

  # build code object
  if len(code) != expected_length :
    raise AssertionError( 'generated code has unexpected length' )

  co = types.CodeType(
            positional_count
          , kwonly_count
          , len(varnames)
          , stackdepth
          , flags
          , bytes(code)
          , constants.as_tuple()
          , names.as_tuple()
          , varnames.as_tuple()
          , filename
          , name
          , lntab.first()
          , lntab.bytes()
          , freevars.as_tuple()
          , cellvars.as_tuple()
          )

  # build function object
  if fglobals is None :
    fglobals = inspect.currentframe().f_back.f_globals

  closure = []
  for k in co.co_freevars :
    closure.append(_make_closure(closure_values[k]))

  fn = types.FunctionType( 
              co
            , fglobals
            , name
            , tuple(positional_defaults) or None
            , tuple(closure) or None
            )

  if keyword_defaults :
    fn.__kwdefaults__ = keyword_defaults

  return fn

