#! /bin/bash
pip3 install build
python3 -m build
python3 -m twine upload dist/* --skip-existing -u $PYPI_USERNAME -p $PYPI_PASSWORD
