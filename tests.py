import unittest
from unittest import TestCase

import byteasm


class TestByteasm(TestCase):
    def testFunctionBuilder(self):
        b = byteasm.FunctionBuilder()
        b.emit_load_const(1)
        b.emit_return_value()
        f = b.make("f")
        self.assertEqual(f(), 1)


if __name__ == "__main__":
    unittest.main()
