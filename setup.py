"""
Flask-MongoSet
-----------------

Access MongoDB from your Flask application

Links
`````

* `documentation <http://packages.python.org/Flask-MongoSet>`_
* `development version
  <https://github.com/Fibio/flask-mongoset/zipball/master#egg=Flask-MongoSet-dev>`_

"""
from setuptools import setup


setup(
    name='Flask-MongoSet',
    version='0.1.1',
    url='https://github.com/Fibio/flask-mongoset',
    license='MIT',
    author='fibio',
    author_email='fibio.tany@gmail.com',
    description='Access MongoDB from your Flask application',
    long_description=__doc__,
    py_modules=[
        'flask_mongoset'
    ],
    test_suite='nose.collector',
    zip_safe=False,
    platforms='any',
    install_requires=[
        'setuptools',
        'Flask',
        'pymongo',
        'trafaret',
    ],
    tests_require=[
        'nose',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
