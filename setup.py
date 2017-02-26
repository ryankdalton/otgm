from setuptools import setup

setup(name='offthegridmaps',
      version='0.4',
      description='OffTheGridMaps',
      author='Ryan Dalton',
      author_email='info@offthegridmaps.com',
      url='http://www.python.org/sigs/distutils-sig/',
      install_requires=['Flask>=0.10.1', 'MarkupSafe' , 'Flask-SQLAlchemy>=1.0', 'gevent==1.1','gunicorn'],
     )
