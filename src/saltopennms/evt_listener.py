import salt.utils.event
from redis import Redis, ConnectionError, ResponseError

event = salt.utils.event.MasterEvent('/var/run/salt/master/')

salt_queue = 'saltq'

evt_generator=event.iter_events(tag='key',full=True)
for data in evt_generator:
    # Example of such data:
    # {'tag': 'key', 'data': {'act': 'accept', 'id': 'minion.host.name','result': True}}
    #

    payload = data['data']
    # minion id
    minion_id    = payload['id']
    # create a redis client
    redis        = Redis(host='127.0.0.1', port=6379, db=0)

    if payload.get('act') == 'accept' and payload.get('result'):
        # process a key add event
        minion_id=("%s/%s" % ('add',minion_id))

    if payload.get('act') == 'delete' and payload.get('result'):
        # process a key delete event
        minion_id=("%s/%s" % ('delete',minion_id))

    redis.rpush(salt_queue, "%s"%(minion_id))
