from optparse import OptionParser
import salt.client, sys, os, hashlib, logging
from salt.exceptions import *
from redis import Redis, ConnectionError, ResponseError

parser = OptionParser()
parser.add_option("-H", "--host", dest="opennms_host",
                  help="OpenNMS host (full url as in http://localhost/opennms/rest)",
                  default="http://localhost/opennms/rest")
parser.add_option("-q", "--quiet",
                  action="store_false", dest="verbose", default=True,
                  help="limit output")
parser.add_option("-n", "--dry-run",
                  action="store_true", dest="dry_run", default=False,
                  help="simulate operations, do not execute them")
parser.add_option("-f", "--force",
                  action="store_true", dest="force", default=False,
                  help="override lock (if present)")
parser.add_option("-u", "--user",
                  dest="user", default="admin",
                  help="OpenNMS user with admin privileges (used to manipulate requisitions through the REST API)")
parser.add_option("-p", "--password",
                  dest="password", default="admin",
                  help="OpenNMS password")

(options, args) = parser.parse_args()

provision_cmd = '/usr/share/opennms/bin/provision.pl --url %s --user %s --password %s '%(options.opennms_host,options.user,options.password)
salt_queue    = 'saltq'
redis         = Redis(host='127.0.0.1', port=6379, db=0)
debug         = options.verbose
dry_run       = options.dry_run
# set up logging
log           = logging.getLogger('consumer')
log.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
log.addHandler(ch)

if not debug:
    log.setLevel(logging.INFO)
    ch.setLevel(logging.INFO)
else:
    log.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)

log.info("Starting (options: dryrun=%s, debug=%s, force=%s, host=%s)"%(dry_run,debug,options.force,options.opennms_host))

# make sure no one else is processing the queue
pid = str(os.getpid())
log.info("PID %s" %(pid))

if not options.force and redis.get('opennms_salt_lock') is not None :
    log.warning( "Process %s is processing the queue, exiting"%(redis.get('opennms_salt_lock')) )
else:
    log.debug( "Locking the queue" )
    redis.set('opennms_salt_lock', pid)
    if redis.get('opennms_salt_lock') != pid :
        log.warning ( "Lock stolen by process with pid %s"%(redis.get('opennms_salt_lock')) )
        exit
    else:
        # expire the lock after 30 minutes in case the process crashes
        log.debug("Add expire timer to lock and set to 30 min")
        redis.expire('opennms_salt_lock', 60*30)

# create a local client object
client               = salt.client.LocalClient()
changed_requisitions = set()

def run_command(command):
    log.debug( "About to run: %s"%(command) )
    if not dry_run:
        return os.system(command)

# add new minions to opennms
for salt_minion in redis.lrange(salt_queue,0,-1):
    minion_id    = salt_minion.split("/")[1]
    action       = salt_minion.split("/")[0]
    if action == 'add':
        try:
            # minion id
            ip_address   = client.cmd(minion_id, 'network.ip_addrs', [])[minion_id][0]
            metadata     = client.cmd(minion_id, 'pillar.data', [])[minion_id]

            # save the minion for processing with opennms only if it has a requisition
            # name in pillar data
            requisition = metadata.get('requisition')
            if requisition :
                # compute nodeid from sha1 of requisition + ipaddress
                sha1 = hashlib.sha1()
                sha1.update("%s%s"%(requisition,ip_address))
                nodeid = sha1.hexdigest()
                # save requisition and id in redis, it will simplify deletion later
                if not dry_run:
                    redis.set(minion_id, "%s/%s"%(requisition,nodeid))
                log.info( "Adding %s[%s] to requisition %s\n\n"%(minion_id,ip_address,requisition) )
                run_command( "%s requisition add %s"%(provision_cmd, requisition) )
                run_command( "%s node add %s %s %s"%(provision_cmd, requisition, nodeid, minion_id) )
                run_command( "%s interface add %s %s %s"%(provision_cmd, requisition, nodeid, ip_address) )
                run_command( "%s interface set %s %s %s snmp-primary P"%(provision_cmd, requisition, nodeid, ip_address) )
                categories = metadata.get('opennms_categories')
                if categories :
                    log.debug( "%s: adding categories"%(minion_id) )
                    for cat in categories.split(','):
                        run_command( "%s category add %s %s %s"%(provision_cmd, requisition, nodeid, cat) )
                else:
                    log.debug( "%s: no categories"%(minion_id) )
                asset = metadata.get('opennms_assetinfo')
                if asset :
                    log.debug( "%s: setting asset info"%(minion_id) )
                    for info in asset.keys():
                        run_command( "%s asset add %s %s %s '%s'"%(provision_cmd, requisition, nodeid, info, asset[info]) )
                else:
                    log.debug( "%s: no asset info"%(minion_id) )
                if not dry_run:
                    redis.lrem(salt_queue, salt_minion, 1)
                changed_requisitions.add(requisition)
            else:
                log.info( "Minion %s has no requisition, skipping"%(minion_id) )
        except SaltReqTimeoutError as timeout:
            log.error( "Salt timeout adding minion %s. Is the minion up?"%(minion_id) )
        except:
            log.error( "Error adding minion %s : %s"%(minion_id, sys.exc_info()[0]) )
    else: #remove
        try:
            nodedata    = redis.get(minion_id)
            if not nodedata:
                log.warning( "No minion data found in redis for %s, will not proceed with delete"%(minion_id) )
            else:
                nodedata    = nodedata.split("/")
                requisition = nodedata[0]
                nodeid      = nodedata[1]
                log.info( "Removing %s (id=%s) from requisition %s"%(minion_id,nodeid,requisition) )
                run_command( "%s node remove %s %s"%(provision_cmd, requisition, nodeid) )
                if not dry_run:
                    redis.lrem(salt_queue, salt_minion, 1)
                changed_requisitions[requisition]=1
        except:
            log.error( "Error removing minion %s : %s"%(minion_id, sys.exc_info()[0]) )

log.info("Finished processing queue")

# import change requisitions
for r in changed_requisitions :
    log.info( "Importing requisition %s"%(r) )
    run_command("%s requisition import %s"%(provision_cmd, r))

# release lock
log.debug("Releasing lock")
redis.delete('opennms_salt_lock')
log.info("Exiting")
