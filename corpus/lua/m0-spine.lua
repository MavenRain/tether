local v = redis.call('INCR', KEYS[1])
return redis.call('GET', KEYS[1])