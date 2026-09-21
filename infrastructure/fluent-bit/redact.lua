local sensitive = {"authorization", "cookie", "csrf", "password", "secret", "token", "signed_url", "credential", "id_card"}

local function redact_value(value)
  if type(value) == "string" then
    for _, key in ipairs(sensitive) do
      value = string.gsub(value, key .. "=([^%s&,;]+)", key .. "=[REDACTED]")
      value = string.gsub(value, key .. ":([^%s&,;]+)", key .. ":[REDACTED]")
    end
    return value
  end
  if type(value) ~= "table" then return value end
  for key, item in pairs(value) do
    local lowered = string.lower(tostring(key))
    local should_redact = false
    for _, pattern in ipairs(sensitive) do
      if string.find(lowered, pattern, 1, true) then should_redact = true break end
    end
    if should_redact then value[key] = "[REDACTED]" else value[key] = redact_value(item) end
  end
  return value
end

function redact(tag, timestamp, record)
  return 1, timestamp, redact_value(record)
end
