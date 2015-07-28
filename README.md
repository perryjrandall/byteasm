`byteasm` is an "assembler" for `python` bytecodes.

Example usage:

```python

import byteasm

b = byteasm.FunctionBuilder()
b.add_positional_arg( 'a' )
b.add_positional_arg( 'b' )
b.emit_load_const( 0 )
b.emit_load_fast( 'a' )
b.emit_compare_lt()
b.emit_pop_jump_if_false( 'l0' )
b.emit_load_fast( 'b' )
b.emit_return_value()
b.emit_label( 'l0' )
b.emit_load_const( None )
b.emit_return_value()
f = b.make( 'f' )

```

The resulting bytecode is:

```  
  1           0 LOAD_CONST               0 (0)
              3 LOAD_FAST                0 (a)
              6 COMPARE_OP               0 (<)
              9 POP_JUMP_IF_FALSE       16
             12 LOAD_FAST                1 (b)
             15 RETURN_VALUE
        >>   16 LOAD_CONST               1 (None)
             19 RETURN_VALUE

```

A visualization facility is also provided that can be of use in understanding the flow of more complex functions:

<img src="https://raw.githubusercontent.com/zachariahreed/pyterminfo/gh-pages/BYTECODE-set_a_foreground.png" width=375>

`byteasm` is a dependency of ![pyterminfo](https://github.com/zachariahreed/pyterminfo).





