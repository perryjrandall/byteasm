from . utils import *

import collections
import functools
import itertools

__all__ = [
    'add_expr'
  , 'atomic_expr'
  , 'cons_expr'
  , 'free_vars'
  , 'head_expr'
  , 'neg_expr'
  , 'Replacement'
  , 'select_expr'
  , 'tail_expr'
  ]


# At present, this code is only used by the visualizer to
# output its representation of the transition functions
# labeling edges of our block graph. An earlier strategey
# for computing stack usage used this code mode fundamentally
# and it may be more useful again in the future

##################################################
#                                                #
##################################################
fully_bound = frozenset()

##################################################
#                                                #
##################################################
def format_function_application( head, *args ) :
  return str.format( '{}({})', head, ','.join(map(str,args)) )

##################################################
#                                                #
##################################################
class Expr( object ) :

  def __repr__( self ) :
    return str(self)

  def __hash__( self ) :
    return hash(self.__class__) ^ hash( self._args() )

  def __eq__( self, other ) :
    return other.__class__ is self.__class__ \
       and other._args() == self._args()

  def __ne__( self, other ) :
    return not (self == other)

  def __neg__( self ) :
    return neg_expr( self )
    
  def __add__( self, other ) :
    return add_expr( self, other )

  def __radd__( self, other ) :
    return add_expr( self, other )

  def __sub__( self, other ) :
    return add_expr( self, -other )

  def __rsub__( self, other ) :
    return add_expr( neg_expr(self), other )


##
class AtomicExpr( Expr ) :

  def __init__( self, key, idx ) :
    self.key  = key
    self.idx  = idx
    self.free = fully_bound if (idx is None) else frozenset((idx,))

  def _args( self ) :
    return self.key, self.idx

  def __str__( self ) :
    if self.idx is None :
      return self.key
    return str.format( '{}.{:04X}', self.key, self.idx )


class NegExpr( Expr ) :

  def __init__( self, term ) :
    self.term = term
    self.free = _free_vars( [term] )

  def _args( self ) :
    return self.term,

  def __str__( self ) :
    return '-' + str(self.term)
 

class HeadExpr( Expr ) :

  def __init__( self, term ) :
    self.term = term
    self.free = _free_vars( [term] )

  def _args( self ) :
    return self.term,

  def __str__( self ) :
    return format_function_application( 'head', self.term )


class TailExpr( Expr ) :

  def __init__( self, term ) :
    self.term = term
    self.free = _free_vars( [term] )

  def _args( self ) :
    return self.term,

  def __str__( self ) :
    return format_function_application( 'tail', self.term )


class AddExpr( Expr ) :

  def __init__( self, *terms ) :
    self.terms = terms
    self.free = _free_vars( list(terms) )

  def _args( self ) :
    return self.terms

  def __str__( self ) :
    result = str( self.terms[0] )
    for t in self.terms[1:] :
      t = str(t)
      if t[0] != '-' :
        result += '+'
      result += t
    return result


class ConsExpr( Expr ) :

  def __init__( self, *terms ) :
    self.terms = terms
    self.free = _free_vars( list(terms) )

  def _args( self ) :
    return self.terms

  def __str__( self ) :
    return format_function_application( 'cons', *self.terms )


class SelectExpr( Expr ) :

  def __init__( self, term0, term1, term2 ) :
    self.term0 = term0
    self.term1 = term1
    self.term2 = term2
    self.free = _free_vars( [term0, term1, term2] )

  def _args( self ) :
    return self.term0, self.term1, self.term2

  def __str__( self ) :
    return format_function_application( 'select', self.term0, self.term1, self.term2 )


##################################################
#                                                #
##################################################
@memoize
def atomic_expr( key, idx ) :
  return AtomicExpr(key,idx)

@memoize
def neg_expr( expr ) :
  if isinstance(expr,int) :
    return -expr
  if isinstance(expr,NegExpr) :
    return expr.term
  if isinstance(expr,AddExpr) :
    return add_expr( *map(neg_expr,expr.terms) )
  return NegExpr( expr )

@memoize
def head_expr( expr ) :
  if isinstance(expr,tuple) :
    return expr[0]
  if isinstance(expr,ConsExpr) :
    return expr.terms[0]
  return HeadExpr( expr )

@memoize
def tail_expr( expr ) :
  if isinstance(expr,tuple) :
    assert expr
    return expr[1:]
  if isinstance(expr,ConsExpr) :
    if len(expr.terms) == 2 :
      return expr.terms[1]
    return cons_expr( *expr.terms[1:] )
  return TailExpr( expr )

@memoize
def add_expr( *exprs ) :

  constant = 0

  counts = collections.defaultdict( lambda : 0 )
  for e in exprs :

    if isinstance(e,AddExpr) :

      for t in e.terms :
        if isinstance(t,int) :
          constant += t
        elif isinstance(t,NegExpr) :
          counts[t.term] -= 1
        else :
          counts[t] += 1

    elif isinstance(e,int) :
      constant += e

    elif isinstance(e,NegExpr) :
      counts[e.term] -= 1

    else :
      counts[e] += 1

  terms = []
  for k,v in counts.items() :
    if v :
      if v < 0 :
        k = neg_expr(k)
        v = -v
      terms.extend( [k]*v )

  if constant :
    terms.append( constant )

  if not terms :
    return 0

  if len(terms) == 1 :
    return terms[0]

  return AddExpr( *terms )

@memoize
def cons_expr( *exprs ) :

  *args,agg = exprs

  if isinstance(agg,ConsExpr) :
    args.extend( agg.terms )
    return cons_expr( *args )

  if isinstance(agg,tuple) :
    args.extend( agg )
    return tuple( args )

  return ConsExpr( *exprs )

@memoize
def select_expr( term0, term1, term2 ) :
  if isinstance(term0,bool) :
    return term1 if term0 else term2
  return SelectExpr( term0, term1, term2 )

##################################################
#                                                #
##################################################
def free_vars( *terms ) :
  return _free_vars( list(terms) )

def _free_vars( terms ) :

  items = []
  for t in terms :
    if isinstance(t,tuple) :
      terms.extend(t)
    elif isinstance(t,Expr) and t.free :
      items.append(t.free)

  if not items :
    return fully_bound

  result = items[0]
  for item in items[1:] :
    if not result.issuperset( item ) :
      result |= item
  return result


##################################################
#                                                #
##################################################
class Replacement( object ) :

  FACTORIES = {
      AddExpr    : add_expr
    , ConsExpr   : cons_expr
    , HeadExpr   : head_expr
    , NegExpr    : neg_expr
    , SelectExpr : select_expr
    , TailExpr   : tail_expr
    }

  def __init__( self, idx, **what ) :
    self._idx  = idx
    self._what = what

  def __call__( self, value ) :

    result = value

    if isinstance(value,AtomicExpr) :
      if value.idx == self._idx :
        result = self._what.get( value.key, value )

    elif isinstance(value,Expr) :
      result = self.FACTORIES[type(value)]( *map(self,value._args()) )

    elif isinstance(value,tuple) :
      result = tuple( map(self,value) )

    if result != value :
      return result

    return value



