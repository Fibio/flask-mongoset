"""
Flask-MongoObject
-----------------

Access MongoDB from your Flask application

Links
`````

* `documentation <http://packages.python.org/Flask-MongoObject>`_
* `development version
  <http://github.com/dqminh/flask-mongoobject/zipball/master#egg=Flask-MongoObject-dev>`_

"""
from setuptools import setup


setup(
    name='Flask-MongoObject',
    version='0.1.1',
    url='https://github.com/dqminh/flask-mongoobject',
    license='MIT',
    author='Fibio',
    author_email='fibio.tany@gmail.com',
    description='Access MongoDB from your Flask application',
    long_description=__doc__,
    # packages=['flaskext'],
    # namespace_packages=['flaskext'],
    py_modules=[
        'flask_mongoobject'
    ],
    # test_suite='nose.collector',
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
