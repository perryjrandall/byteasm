import opcode

##################################################
#                                                #
##################################################
CO_OPTIMIZED      = 0x0001
CO_NEWLOCALS      = 0x0002
CO_VARARGS        = 0x0004
CO_VARKEYWORDS    = 0x0008
CO_NESTED         = 0x0010
CO_GENERATOR      = 0x0020
CO_NOFREE         = 0x0040

COMPARE_LT        = opcode.cmp_op.index( '<' )
COMPARE_LE        = opcode.cmp_op.index( '<=' )
COMPARE_EQ        = opcode.cmp_op.index( '==' )
COMPARE_NE        = opcode.cmp_op.index( '!=' ) 
COMPARE_GT        = opcode.cmp_op.index( '>' )
COMPARE_GE        = opcode.cmp_op.index( '>=' )
COMPARE_IN        = opcode.cmp_op.index( 'in' )
COMPARE_NOT_IN    = opcode.cmp_op.index( 'not in' )
COMPARE_IS        = opcode.cmp_op.index( 'is' )
COMPARE_IS_NOT    = opcode.cmp_op.index( 'is not' )
COMPARE_EXCEPTION = opcode.cmp_op.index( 'exception match' )

NilArg            , \
GenericArg        , \
AbsLabelArg       , \
RelLabelArg       , \
ConstantArg       , \
FreeVariableArg   , \
NameArg           , \
LocalArg          = range(8)

IP_START          = -1
IP_END            = 0xFFFFFFFF
IP_EXCEPT         = 0xFFFFFFFE

##################################################
#                                                #
##################################################
globals().update( opcode.opmap )

##################################################
#                                                #
##################################################
del opcode 
