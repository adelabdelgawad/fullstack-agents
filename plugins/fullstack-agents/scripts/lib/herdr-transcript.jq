def clip($n): if type == "string" then (if length > $n then .[0:$n] + " …" else . end) else tostring | clip($n) end;
def args: (.command // .description // .file_path // .pattern // .prompt // .query // .url // (tostring)) | clip(200);
def result_text: if type == "array" then map(.text? // "") | join("\n") else tostring end;

fromjson? // empty
| select(.type == "user" or .type == "assistant")
| .message as $m
| if ($m.content | type) == "string" then "\n■ brief\n" + ($m.content | clip(1500))
  else $m.content[]
    | if .type == "text" then "\n▌ " + .text
      elif .type == "thinking" and ((.thinking // "") | length) > 0 then "  · " + (.thinking | gsub("\n"; " ") | clip(300))
      elif .type == "tool_use" then "→ " + .name + ": " + (.input | args)
      elif .type == "tool_result" then "← " + (.content | result_text | split("\n") | .[0:12] | join("\n  ") | clip(1200))
      else empty end
  end
