"""
Flask-MongoObject
-----------------

Access MongoDB from your Flask application

Links
`````

* `documentation <http://packages.python.org/Flask-MongoObject>`_
* `development version
  <https://github.com/MediaSapiens/flask-mongoobject/zipball/master#egg=Flask-MongoObject-dev>`_

"""
from setuptools import setup


setup(
    name='Flask-MongoObject',
    version='0.1',
    url='https://github.com/MediaSapiens/flask-mongoobject',
    license='MIT',
    author='Yehor Nazarkin, Tatyana Kuznetsova',
    author_email='nimnull@gmail.com, fibio.tany@gmail.com',
    description='Access MongoDB from your Flask application',
    long_description=__doc__,
    py_modules=['flask_sqlalchemy'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        'setuptools',
        'Flask',
        'pymongo',
        'trafaret',
        'py.test'
    ],
    test_suite='mongoobject_test.flask_mongoobject',
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
