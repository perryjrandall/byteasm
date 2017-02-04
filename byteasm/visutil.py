from . utils import *

import html
import io
import os
import posixpath

__all__ = [
    'Table'
  , 'Tagged'
  , 'make_visualization_hook_manager'
  ]

##################################################
#                                                #
##################################################
class Tagged( object ) :

  @classmethod
  def ensure( cls, value ) :
    if not isinstance(value,cls) :
      value = cls(value)
    return value

  def __init__( self, value, *, limit=50, color=None, **kwargs ) :
    self.value  = value
    self.limit  = limit
    self.color  = color
    self.kwargs = kwargs

  def write( self, buf ) :
    buf.write( '<td' )
    for kv in self.kwargs.items() :
      buf.write( str.format( ' {}="{}"', *kv ) )
    buf.write( '>' )
    if self.value not in (None,'') :
      if self.color :
        buf.write( '<font color="' )
        buf.write( self.color )
        buf.write( '">' )
      value = html.escape( str(self.value), False ) \
                  .replace( '{', r'\\x7b' ) \
                  .replace( '}', r'\\x7d' )
      if len(value) > self.limit :
        value = value[:self.limit-3] + '...'
      buf.write( value )
      if self.color :
        buf.write( '</font>' )
    buf.write( '</td>' )


class Table( object ) :

  def __init__( self, **kwargs ) :
    self._params = kwargs
    self._rows   = []

  def __bool__( self ) :
    return bool(self._rows)

  def add( self, *row ) :
    self._rows.append( tuple( Tagged.ensure(c) for c in row  ) )

  def __str__( self ) :
    buf = io.StringIO()
    buf.write( '<<table' )
    for kv in self._params.items() :
      buf.write( str.format( ' {}="{}"', *kv ) )
    buf.write( '>' )
    for row in self._rows :
      buf.write( '<tr>' )
      for col in row :
        col.write( buf )
      buf.write( '</tr>' )
    buf.write( '</table>>' )
    return buf.getvalue()


##################################################
#                                                #
##################################################
def make_visualization_hook_manager( mod, f ) :

  def set_visualization_path( path, fmt='{}.png', filter=None ) :

    impl = PASS

    if path is not None :

      path = posixpath.expanduser( path )

      curr = ''
      for p in path.split( '/' ) :
        curr += '/' + p
        if not os.path.exists( curr ) :
          os.mkdir( curr )

      path += '/' + fmt 

      def impl( name, value ) :
        if (filter is None or filter(name)) :
          f( value, path.format( name ) )

    mod._visualization_hook = impl

  return set_visualization_path



