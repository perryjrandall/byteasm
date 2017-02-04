from . import assemble
from . aexpr import *
from . constants import *
from . stack import *
from . visutil import *

import opcode
import pygraphviz
import types

__all__ = [
    'visualize'
  ]

##################################################
#                                                #
##################################################
globals().update( opcode.opmap )

##################################################
#                                                #
##################################################
def format_offset( idx ) :
  return format( idx, '04X' )

def effect_expr_str( effect ) :
  return str( effect( *(atomic_expr(v,None) for v in 'SFE') ) )

##################################################
#                                                #
##################################################
def visualize( se, output, indicate_dead=True ) :

  G = pygraphviz.AGraph( directed=True )

  blocks = make_annotated_cfg( se )

  for ip,blk in sorted(blocks.items()) :

    if ip == IP_START :
      G.add_node( ip, label='START', rank='source' )

    elif ip == IP_END :
      G.add_node( ip, label='END', rank='sink' )

    elif ip == IP_EXCEPT :
      G.add_node( ip, label='EXCEPT', rank='sink' )

    else :

      tab = Table( border=0, cellborder=0, cellpadding=3, bgcolor="white" )

      for opip,_,op,raw,_,_,delta in blk.instructions :

        if op in opcode.hasjrel or op in opcode.hasjabs :
          raw = format_offset( raw )
        elif op == LOAD_CONST :

          if isinstance(raw,(types.MethodType,types.BuiltinMethodType)) :
            raw = str.format( '#{}', getattr( raw, 'pretty_name', raw.__qualname__ ) )

          elif isinstance(raw,(types.FunctionType,types.BuiltinFunctionType)) :
            raw = str.format( '#{}', getattr( raw, 'pretty_name', raw.__name__ ) )

          else :
            raw = repr(raw)
            raw = raw.replace( '{', '\\x7b' )
            raw = raw.replace( '}', '\\x7d' )

        elif op < opcode.HAVE_ARGUMENT :
          raw = ''

        tab.add( 
            format_offset(opip)
          , Tagged( 
                '{} {}'.format( opcode.opname[op], raw )
              , align='left'
              )
          , Tagged(
                delta 
              , align='right'
              , color='blue' 
              )
          )

      for args in blk.values :

        tab.add( 
            Tagged( 
                's:{} f:{} e:{}'.format( *args )
              , colspan=3
              , bgcolor="gray"
              )
          )

      G.add_node( ip, shape='record', label=str(tab) )


  for source_ip,sblk in sorted(blocks.items()) :
    for target_ip,(s_effect,b_effect,e_effect,no_follow) in sblk.targets.items() :

      params = {}

      if indicate_dead and no_follow is not None :
        if all( no_follow(*args) for args in sblk.values ) :
          params[ 'color' ] = 'red'

      tab = Table( border=0, cellborder=0, cellpadding=0, bgcolor='white' )
      for var,effect in (('S',s_effect),('F',b_effect),('E',e_effect)) :
        effect = effect_expr_str(effect)
        if effect != var :
          tab.add(
               Tagged( effect, align='right', color='blue' )
             , Tagged( '→', align='right', color='blue' )
             , Tagged( var, align='left', color='blue' )
             )

      if tab :
        params[ 'label' ] = str(tab)

      G.add_edge( source_ip, target_ip, **params )

  G.draw( output, prog='dot' )



##################################################
#                                                #
##################################################
set_visualization_path = make_visualization_hook_manager( assemble, visualize )



