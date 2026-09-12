module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
type value = Data of E.tid * int * value list | Fields of value list
  | Literal of Kanon_kernel.Literal.t | Closure of string * int * value list
  | Script of string | Reply of int | Erased
type finish = Answer of int | Failure
type plan = { invokes : string list; finish : finish }
let first_order = Error "SH-FIRST-ORDER expected closed, straight-line Client Reply control"

(* Normalize static helpers only. Replies stay symbolic; client loops cannot run here. *)
let plan ~budget rows ~entry =
  let functions = Flags.functions rows in
  let lookup n = List.assoc_opt n functions |> Option.to_result ~none:("SH-GLOBAL " ^ n) in
  let rec eval env term =
    if Kanon_kernel.Budget.exhausted budget then Error "SH-BUDGET" else
    let many xs = Lua.all (List.map (eval env) xs) in
    match term with
    | E.KVar i -> Kanon_kernel.Rules.at i env |> Option.to_result ~none:"SH-VAR"
    | E.KLit l -> Ok (Literal l)
    | E.KErased -> Ok Erased
    | E.KGlobal n ->
        let* ps, r, b = lookup n in
        if ps <> [] then Ok (Closure (n, List.length ps, []))
        else if r = E.RUnion (E.Tid "mu<Script>") then Ok (Script n) else eval [] b
    | E.KClos (E.Fid n, arity, xs) -> let* xs = many xs in Ok (Closure (n, arity, xs))
    | E.KApp (f, xs) | E.KTail (f, xs) ->
        let* f = eval env f in let* xs = many xs in
        let constructor = match f with
          | Closure ("tetherCtor_inv", 2, []) -> true
          | Closure _ | Data _ | Fields _ | Literal _ | Script _ | Reply _ | Erased -> false in
        if List.exists (function Closure _ -> true
          | Data _ | Fields _ | Literal _ | Script _ | Reply _ | Erased -> false) xs && not constructor
        then first_order else apply f xs
    | E.KLet (_n, x, b) -> let* x = eval env x in eval (x :: env) b
    | E.KTag (tid, tag, xs) -> let* xs = many xs in Ok (Data (tid, tag, xs))
    | E.KStruct (_tid, xs) -> let* xs = many xs in Ok (Fields xs)
    | E.KProj (_tid, i, x) ->
        let* x = eval env x in (match x with
        | Fields xs -> Kanon_kernel.Rules.at i xs |> Option.to_result ~none:"SH-PROJECTION"
        | Data _ | Literal _ | Closure _ | Script _ | Reply _ | Erased -> first_order)
    | E.KCase (_tid, x, bs) ->
        let* x = eval env x in (match x with
        | Data (_t, tag, xs) ->
            let* b = List.find_opt (fun (b : E.kbranch) -> b.tag = tag) bs
              |> Option.to_result ~none:"SH-CASE" in
            if List.length xs = b.arity then eval (List.rev xs @ env) b.body else first_order
        | Fields _ | Literal _ | Closure _ | Script _ | Reply _ | Erased -> first_order)
    | E.KDelay _ | E.KForce _ -> first_order
  and apply f xs = match f with
    | Closure (n, arity, captures) ->
        let* ps, _r, b = lookup n in
        if arity = List.length xs && List.length ps = List.length captures + arity
        then eval (List.rev (captures @ xs)) b else first_order
    | Data _ | Fields _ | Literal _ | Script _ | Reply _ | Erased -> first_order in
  let rec walk calls value = match value with
    | Data (E.Tid "mu<Client>", 0, [Reply answer]) ->
        Ok { invokes = List.rev calls; finish = Answer answer }
    | Data (E.Tid "mu<Client>", 1, [Script script; continuation]) ->
        let* next = apply continuation [Reply (List.length calls)] in
        walk (script :: calls) next
    | Data (E.Tid "mu<Client>", 2, [_fault]) -> Ok { invokes = List.rev calls; finish = Failure }
    | Data _ | Fields _ | Literal _ | Closure _ | Script _ | Reply _ | Erased -> first_order in
  let* ps, r, body = lookup entry in
  if ps <> [] || r <> E.RUnion (E.Tid "mu<Client>") then first_order
  else let* value = eval [] body in walk [] value

let header = {|#!/bin/bash
set -eu
[ "$(jq --version)" = 'jq-1.6' ] || exit 4
: "${TETHER_URL:?TETHER_URL is required}"
: "${TETHER_TOKEN:?TETHER_TOKEN is required}"
post() {
  env_json=$(curl -q -fsS --proto '=http,https' --max-time 30 -X POST "$TETHER_URL" \
    -H "Authorization: Bearer $TETHER_TOKEN" -H 'Content-Type: application/json' \
    --data-binary "$body") || { printf '%s\n' 'TETHER Network or Http fault' >&2; exit 4; }
}
envelope() {
  kind=$(printf '%s' "$env_json" | jq -er '
    if type != "object" or length != 1 then "invalid"
    elif has("result") then .result | type
    elif has("error") and (.error | type == "string") then "error"
    else "invalid" end') || exit 4
  case "$kind" in
    number|string|array|null|error) ;;
    *) exit 4 ;;
  esac
}
fault() {
  printf '%s' "$env_json" | jq -r '.error' >&2
  exit 4
}
load() {
  body=$(jq -n --args '$ARGS.positional' SCRIPT LOAD "$2") || exit 4
  post
  envelope
  [ "$kind" != error ] || fault
  [ "$kind" = string ] || exit 4
  printf '%s' "$env_json" | jq -e --arg sha "$1" '.result == $sha' > /dev/null || exit 4
}
invoke() {
  sha="$1"; lua="$2"; suffix="$3"; shift 3
  body=$(jq -n --args '$ARGS.positional' "EVALSHA$suffix" "$sha" "$#" "$@") || exit 4
  post
  envelope
  if [ "$kind" = error ]; then
    if printf '%s' "$env_json" | jq -e '.error == "NOSCRIPT" or (.error | startswith("NOSCRIPT "))' > /dev/null; then
      body=$(jq -n --args '$ARGS.positional' "EVAL$suffix" "$lua" "$#" "$@") || exit 4
      post
      envelope
    fi
  fi
  [ "$kind" != error ] || fault
  printf '%s' "$env_json" | jq -e '
    def safe: if type == "number" then floor == . and . >= -9007199254740991 and . <= 9007199254740991
      elif type == "array" then all(.[]; safe)
      else type == "null" or type == "string" end;
    .result | safe' > /dev/null || exit 4
}
reply() {
  env_json="$1"
  envelope
  case "$kind" in
    number) printf '%s' "$env_json" | jq -r '.result | tostring' || exit 4 ;;
    string) printf '%s' "$env_json" | jq -r '.result' || exit 4 ;;
    array) printf '%s' "$env_json" | jq -c '.result' || exit 4 ;;
    null) printf '\n' ;;
    error) fault ;;
    *) exit 4 ;;
  esac
}
|}

let key ns =
  if List.exists (fun n -> n <= 0 || n > 127) ns then Error "SH-KEY-TEXT expected non-NUL ASCII key"
  else Ok ("$'" ^ String.concat "" (List.map (Printf.sprintf "\\%03o") ns) ^ "'")

let emit plan artifacts =
  let numbered = List.mapi (fun i (name, a) -> name, (string_of_int i, a)) artifacts in
  let* bodies = Lua.all (List.map (fun (_name, (i, (a : Lua.artifact))) ->
    let marker = "TETHER_LUA_" ^ a.sha1 in
    if List.mem marker (String.split_on_char '\n' a.body) || String.contains a.body '\000'
    then Error "SH-HEREDOC invalid body" else
    Ok ("IFS= read -r -d '' lua" ^ i ^ " <<'" ^ marker ^ "' || :\n" ^ a.body ^ "\n" ^
      marker ^ "\nlua" ^ i ^ "=\"${lua" ^ i ^ "%?}\"\nloaded" ^ i ^ "=0\n")) numbered) in
  let* calls = Lua.all (List.mapi (fun call name ->
    let* i, a = List.assoc_opt name numbered |> Option.to_result ~none:("SH-SCRIPT " ^ name) in
    let* keys = Lua.all (List.map key a.Lua.keys) in
    Ok ("if [ \"$loaded" ^ i ^ "\" = 0 ]; then\n  load '" ^ a.sha1 ^ "' \"$lua" ^ i ^
      "\"\n  loaded" ^ i ^ "=1\nfi\ninvoke '" ^ a.sha1 ^ "' \"$lua" ^ i ^ "\" " ^
      (if a.no_writes then "'_RO' " else "'' ") ^ String.concat " " keys ^ "\nreply" ^ string_of_int call ^ "=\"$env_json\"\n")) plan.invokes) in
  let finish = match plan.finish with
    | Answer i -> "reply \"$reply" ^ string_of_int i ^ "\"\n"
    | Failure -> "printf '%s\\n' 'TETHER Client fault' >&2\nexit 4\n" in
  Ok (header ^ "# TETHER-BODIES-BEGIN\n" ^ String.concat "" bodies ^
    "# TETHER-BODIES-END\n" ^ String.concat "" calls ^ finish)
