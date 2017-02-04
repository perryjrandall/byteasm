from . aexpr import *
from . constants import *
from . utils import *

import collections
import functools
import opcode

__all__ = [
    'StackEffects'
  , 'compute_stack_depth'
  , 'make_annotated_cfg'
  ]


##################################################
#                                                #
##################################################
class Block( object ) :

  def __init__( self ) :
    self.instructions        = []
    self.targets             = {}
    self.delta               = 0
    self.max_delta           = 0
    self.delta_includes_last = True


##
class StackEffects( object ) :

  # Partitions the instruction stream into a directed graph of 
  # blocks. A block is closed when:
  #
  #   * a label is encountered
  #   * the instruction pointer is affected in a non-trivial way
  #   * the block stack if modified
  #   * the exception state is modified
  #
  # Edges between nodes of the resulting graph are labeled with a 
  # set of functions that describe updates to the cpython interpreter
  # value stack, block stack, and exception state between the
  # exit from and entry to the connected blocks. Blocks may
  # themselves also describe changes to the value stack that
  # occur through execution of instructions contained within

  _effects = None

  def __init__( self, labels ) :

    cls = self.__class__
    if cls._effects is None :
      cls._effects = _make_effects_tab()

    labeled = collections.defaultdict( list )
    for k,v in labels.items() :
      labeled[ v ].append( k )

    self._blk      = None
    self._labeled  = labeled
    self._blocks   = {}

  def blocks( self ) :
    return self._blocks.items()

  def insert( self, ip, oplen, op, raw, arg, typ ) :

    ip_next = ip + oplen

    blk = self._blk
    if blk is None :
    
      blk = Block()

      self._blocks[ ip ] = blk
      self._blk = blk

    apply_delta,force_flush,targets = self._effects[op]

    delta = None
    if apply_delta :
      blk.delta += opcode.stack_effect( op, arg )
      blk.max_delta = max( blk.max_delta, blk.delta )
      delta = blk.delta

    blk.instructions.append((ip,oplen,op,raw,arg,typ,delta))

    if force_flush or ip_next in self._labeled :
      for dst,*eff in targets :
        blk.targets[dst( ip_next, raw )] = eff
      blk.delta_includes_last = (delta is not None)
      self._blk = None



##
def _make_effects_tab() :

  def AdjustValueStack( delta ) :
    return (lambda s,b,e : s+delta)

  def PopFrameStack( s, b, e ) :
    return tail_expr(b)

  def PeekFrameStack( s, b, e ) :
    return head_expr(b)

  def PushFrameStack( s, b, e ) :
    return cons_expr(s,b)

  def Next( se=None, fe=None, ee=None, ne=None ) :
    return first, se, fe, ee, ne

  def Arg( se=None, fe=None, ee=None, ne=None ) :
    return second, se, fe, ee, ne

  def Other( ip, se=None, fe=None, ee=None, ne=None ) :
    return constantly(ip), se, fe, ee, ne

  def impl( *defs ) :

    effects = [None] * 256
    for ops, typ, *rest in defs :
      
      apply_delta = not (typ&2)
      force_flush = bool(typ&1)

      targets = []
      for ip,se,fe,ee,ne in rest :

        if se is None :
          se = first
        elif isinstance(se,int) :
          se = AdjustValueStack(se)

        if fe is None :
          fe = second

        if ee is None :
          ee = third
        elif isinstance(ee,bool) :
          ee = constantly(ee)

        targets.append((ip,se,fe,ee,ne))

      targets = tuple(targets)

      for op in ((ops,) if isinstance(ops,int) else ops) :
        effects[op] = (apply_delta,force_flush,targets)

    return effects

  ##
  return impl(
      ( opcode.opmap.values() , 0 , Next()                                                                )
    , ( opcode.hasjrel        , 1 , Next(), Arg()                                                         )
    , ( opcode.hasjabs        , 1 , Next(), Arg()                                                         )
    , ( RAISE_VARARGS         , 1 , Other( IP_EXCEPT )                                                    )
    , ( RETURN_VALUE          , 1 , Other( IP_END )                                                       )
    , ( CONTINUE_LOOP         , 3 , Arg()                                                                 )
    , ( END_FINALLY           , 3 , Next( se=(lambda s,b,e:select_expr(e,s-6,s-1)), ee=False, ne=third )  )
    , ( FOR_ITER              , 3 , Next( se=1 ), Arg( se=-1 )                                            )
    , ( JUMP_ABSOLUTE         , 3 , Arg()                                                                 )
    , ( JUMP_FORWARD          , 3 , Arg()                                                                 )
    , ( JUMP_IF_FALSE_OR_POP  , 3 , Next( se=-1 ), Arg()                                                  )
    , ( JUMP_IF_TRUE_OR_POP   , 3 , Next( se=-1 ), Arg()                                                  )
    , ( POP_BLOCK             , 3 , Next( se=PeekFrameStack, fe=PopFrameStack )                           )
    , ( POP_EXCEPT            , 3 , Next( se=PeekFrameStack, fe=PopFrameStack, ee=False )                 )
    , ( SETUP_EXCEPT          , 3 , Next( fe=PushFrameStack ), Arg( se=6, fe=PushFrameStack, ee=True )    )
    , ( SETUP_FINALLY         , 3 , Next( fe=PushFrameStack, ee=False ), Arg( se=6, ee=True )             )
    , ( SETUP_LOOP            , 3 , Next( fe=PushFrameStack ), Arg()                                      )
    , ( SETUP_WITH            , 3 , Next( se=1, fe=PushFrameStack ), Arg( se=7, ee=True )                 )
    )



##################################################
#                                                #
##################################################
class ExtendedBlock( object ) :
  pass


##
def _make_extended_blocks( se, merge=True ) :

  # FIXME - merge flag is currently doing nothing

  # From an input graph linked from source to target,
  # create a graph (of reachable blocks) that is 
  # bi-directionally linked. Optionally, we simplify
  # graphs by getting rid of blocks that consist of 
  # a single, unconditional jump

  sources = collections.defaultdict( lambda : collections.defaultdict(list) )

  xblocks = { IP_START  : Block(), IP_END    : Block() , IP_EXCEPT : Block() }
  xblocks[ IP_START ].targets[ 0 ] = (first,second,third,None)
  xblocks.update( se.blocks() )

  for ip,blk in xblocks.items() :
    for tgt,info in blk.targets.items() :
      sources[tgt][ip].append( info )

  pending = set( xblocks.keys() )
  pending.discard( IP_START )
  while pending :

    ip = pending.pop()
    if sources[ip] :
      continue

    blk = xblocks[ip]
    for k in blk.targets.keys() :
      sources[k].pop( ip, None )
      pending.add( k )
    blk.targets.clear()


  blocks = {}
  for ip, blk in xblocks.items() :
    block_sources = []
    for src,items in sources[ip].items() :
      for v in items :
        block_sources.append( (src,) + tuple(v) )
    if block_sources or ip == IP_START :

      ext = ExtendedBlock()
      ext.instructions        = blk.instructions
      ext.delta_includes_last = blk.delta_includes_last
      ext.delta               = blk.delta
      ext.max_delta           = blk.max_delta
      ext.targets             = blk.targets
      ext.sources             = block_sources
      ext.dependents          = set( blk.targets.keys() )
      ext.values              = set()

      blocks[ip] = ext


  return blocks


##################################################
#                                                #
##################################################
def _compute_stack_usage( blocks, n=1000 ) :

  # Computes usage of the cpython value stack by abstract interpretation.
  # To compute this information, it is necessary to also calculate
  # block-stack usage and some exception state information which
  # is also returned. (In particular the cpython bytecode compiler
  # generates some usages of END_FINALLY that depend on the fact
  # that an exception will always be reraised). Calculation proceeds 
  # by simple propagation of know values, iterating until steady state.

  blocks[IP_START].values = {(0,(),False)}

  pending = {0}

  for _ in range(n) :

    if not pending :
      break

    ip = pending.pop()
    blk = blocks[ip]

    options = set()
    for src,s_expr,f_expr,e_expr,no_follow in blk.sources :
      for args in blocks[src].values :
        if no_follow is None or not no_follow(*args) :
          options.add((s_expr(*args), f_expr(*args), e_expr(*args)))

    current = set()
    for option in options :
      
      # with out current solution strategy, there shouldn't 
      # be any free variables. 

      values = [option]
      for free in free_vars( *option ) :

        fblk = blocks[free]
        fblk.dependents.add( ip )
        if fblk.values :

          new = []
          for fs,ff,fe in fblk.values :
            new.extend( map(Replacement( free, S=fs, F=ff, E=fe ),values) )
          values = new

      for s,f,e in values :
        current.add((s+blk.delta,f,e))

    if current != blk.values :
        blk.values = current
        pending.update( blk.dependents )

  if pending :
    raise Exception( 'convergence failure' )


##################################################
#                                                #
##################################################
def make_annotated_cfg( se, compute=True ) :

  blocks = _make_extended_blocks( se )
  if compute :
    _compute_stack_usage( blocks )
  return blocks


def compute_stack_depth( se, **kwargs ) :

  blocks = _make_extended_blocks( se )
  _compute_stack_usage( blocks, **kwargs )

  max_stack = 0
  for blk in blocks.values() :
    for s,_,_ in blk.values :
      assert isinstance(s,int), s
      max_stack = max( max_stack, s-blk.delta+blk.max_delta )

  return max_stack




