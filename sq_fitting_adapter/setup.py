from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

# fetch some values from package.xml
setup_args = generate_distutils_setup(
    packages=['sq_fitting_adapter'],
    package_dir={'': 'src'})

setup(**setup_args)
