# Point d'entrée legacy — préférer : python -m unittest tests.unit.test_dice -v
"""Compatibilité : redirige vers tests.unit.test_dice."""
import unittest

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.unit.test_dice")
    runner = unittest.TextTestRunner(verbosity=2)
    raise SystemExit(not runner.run(suite).wasSuccessful())
