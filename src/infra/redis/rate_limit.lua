-- Sliding window rate limiter
-- KEYS[1] = rate_limit key
-- ARGV[1] = window size in seconds
-- ARGV[2] = max requests
-- ARGV[3] = current timestamp (seconds)

local now = tonumber(ARGV[3])
local window = tonumber(ARGV[1])
local max_requests = tonumber(ARGV[2])
local window_start = now - window

-- Remove old entries
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', window_start)

-- Count current entries
local count = redis.call('ZCARD', KEYS[1])

if count >= max_requests then
    -- Get the oldest entry timestamp for Retry-After
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry_after = 0
    if oldest[2] then
        retry_after = math.ceil(window_start + window - tonumber(oldest[2]))
        if retry_after < 0 then retry_after = 0 end
    end
    return {0, count, retry_after}
end

-- Add current request
redis.call('ZADD', KEYS[1], now, ARGV[4] or now)
redis.call('EXPIRE', KEYS[1], window)

local remaining = max_requests - count - 1
return {1, count + 1, remaining}
