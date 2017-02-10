import sys
from setuptools import setup

__author__  = 'Zachariah Reed'
__version__ = '0.2'
__contact__ = 'zreed@fastmail.com'
__url__     = 'https://github.com/zachariahreed/byteasm'
__license__ = 'GPL'

if sys.version_info < (3,6) :
  raise NotImplementedError( 'byteasm requires Python 3.6+' )

setup(
    name         = 'byteasm'
  , version      = __version__
  , description  = 'an assembler for python bytecode'
  , author       = __author__
  , author_email = __contact__
  , url          = __url__
  , packages     = ['byteasm']
  , license      = __license__
  , platforms    = 'any'
  , download_url = 'https://github.com/zachariahreed/byteasm/tarball/' + __version__
  , classifiers  = [
                        'Development Status :: 4 - Beta'
                      , 'Intended Audience :: Developers'
                      , 'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)'
                      , 'Programming Language :: Python :: 3 :: Only'
                      , 'Programming Language :: Python :: 3.6'
                      ]
  )
