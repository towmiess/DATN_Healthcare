local key = KEYS[1]
local max_attempt = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

local current = redis.call("GET", key)

if current == false then
	redis.call("SET", key, 1, "EX", ttl)
	return 1
end

current = tonumber(current) + 1
redis.call("INCR", key)

if current > max_attempt then
	return -1
end

return current