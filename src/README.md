Python scripts implementing integration between Salt Stack and OpenNMS.

How it works
============

The listener script hooks up to the event notification API that
was added to Salt in 0.10.5.

Key add and delete events are stored into a Redis queue for
later batch processing by the consumer script. The consumer
script can be invoked from cron every 30 minutes and
will use the provision.pl script to push minions into an
opennms provioning requisition.

Requirements
------------

The listener and consumer scripts must be run on the Salt master.
Other than Salt they require:

* Redis
* the python-redis module
* a local copy of provision.pl

On Ubuntu the dependency can be met by running:

``apt-get install redis-server python-redis``

Some distributions (Centos5 for sure) ship with a very old version of python-redis.
If you encounter errors running the event listener about a RPUSH function not being found
you need to upgrade. To upgrade the python-redis module use easy install:

     easy_install redis



Running the event listener
--------------------------

On upstart-enabled systems (Centos 6, Ubuntu 12.04) you can use
the upstart script in the scripts folder to have the event listener
start together with the salt-master.

