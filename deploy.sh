#! /bin/bash
python3 setup.py sdist bdist_wheel
python3 -m twine upload dist/* --skip-existing -u $PYPI_USERNAME -p $PYPI_PASSWORD
