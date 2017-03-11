# Setup script for ink package
from setuptools import setup

setup(name = 'ink',
      version = '1.0',
      description = 'Backup manager',
      author = 'Katie Jones',
      author_email = 'k.jo133@gmail.com',
      url = 'https://github.com/katie-jones/ink',
      py_modules = ['ink'],
      entry_points = {
          'console_scripts': ['run_ink=ink:main_from_command_line']
      }
      )
