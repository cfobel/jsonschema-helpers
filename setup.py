try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

import sys
sys.path.insert(0, '.')
import version


setup(name='jsonschema-helpers',
      version=version.getVersion(),
      author='Christian Fobel',
      author_email='christian@fobel.net',
      url='https://github.com/cfobel/jsonschema-helpers',
      license='LGPL-3.0',
      install_requires=['jsonschema>=2.5.1'],
      packages=['jsonschema_helpers'])
