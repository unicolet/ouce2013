Salt-OpenNMS integration
========================

For an explanation of what this integration does check out
the presentation in the top folder (the index.html file).

Event listener service
----------------------

The scripts folder contains the upstart service definition
for the Salt event listener process.

For systems that support upstart like Ubuntu and Centos 6
copy the *saltopennms.conf* file in */etc/init* on the Salt master,
then edit it and adjust the paths.

Start the listener by running:

    start saltopennms

For systems that don't support upstart you can start the service
by adding a line like the following to */etc/inittab*:

    SO:2345:respawn:/usr/bin/python /root/ouce2013/src/saltopennms/evt_listener.py >> /var/log/saltopennms.log 2>&1

Adjust the paths as required by your system and start the service:

    telinit q

In both cases the service will be restarted if it crashes.

Consumer
--------

The consumer is reponsible for batch processing events queued by the event
listener and forwarding the results to the OpenNMS server through
*provision.pl* calls.

Simply start the consumer from crontab, for instance every 30 minutes:

     0,30 *    * * *   root /root/ouce2013/src/saltopennms/consumer.py [ADD YOUR OPTIONS] >> /var/log/saltopennms_consumer.log 2>&1

*Remember*: to set the correct options for your environment. To find out
which ones are available run:

     consumer.py --help

Installing provision.pl
-----------------------

*provision.pl* is property of the OpenNMS project.

The integration uses a local copy of *provision.pl*. There is a
recent version of provision.pl in the saltopennms folder.

If your system does not have all perl dependencies required by
provision.pl you can install them by either using the package manager
of your distribution of choice or using CPAN.

Example of using CPAN:

     perl -MCPAN -e shell
     cpan > install [ModuleName]



