module Keys = Map.Make (String)
module Members = Set.Make (String)
type data = Str of string | Hash of (string * string) list | List of string list
  | Set of string list | ZSet of (string * string) list | Stream of (string * string) list
type t = data Keys.t
type fault = Wrong_type | Not_integer | Hash_not_integer | Overflow
let empty = Keys.empty
let put = Keys.add
let message = function
  | Wrong_type -> "WRONGTYPE Operation against a key holding the wrong kind of value"
  | Not_integer -> "ERR value is not an integer or out of range"
  | Hash_not_integer -> "ERR hash value is not an integer"
  | Overflow -> "ERR increment or decrement would overflow"
let get key store = Keys.find_opt key store |> Option.fold ~none:(Ok None) ~some:(function
  | Str value -> Ok (Some value)
  | Hash _ | List _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
let integer text = Result.bind (Int64.of_string_opt text |> Option.to_result ~none:Not_integer)
  (fun value -> if Int64.to_string value = text then Ok value else Error Not_integer)
let set key value store = "OK", put key (Str value) store
let exists key store = if Keys.mem key store then "1" else "0"
let del key store = exists key store, Keys.remove key store
let ( let* ) = Result.bind
let add value amount =
  if (amount > 0L && value > Int64.sub Int64.max_int amount)
    || (amount < 0L && value < Int64.sub Int64.min_int amount) then Error Overflow
  else Ok (Int64.to_string (Int64.add value amount))
let incrby key amount store =
  let* amount = integer amount in let* value = get key store in
  let* value = integer (Option.value ~default:"0" value) in
  let* text = add value amount in Ok (text, put key (Str text) store)
let incr key store = incrby key "1" store
let decr key store = incrby key "-1" store
let hash key store = Keys.find_opt key store |> Option.fold ~none:(Ok Keys.empty) ~some:(function
  | Hash fields -> Ok (Keys.of_seq (List.to_seq fields))
  | Str _ | List _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
let save_hash key fields store =
  if Keys.is_empty fields then Keys.remove key store else put key (Hash (Keys.bindings fields)) store
let hget key field store = let* fields = hash key store in Ok (Keys.find_opt field fields)
let hexists key field store = let* fields = hash key store in Ok (if Keys.mem field fields then "1" else "0")
let hlen key store = let* fields = hash key store in Ok (string_of_int (Keys.cardinal fields))
let hset key field value store = let* fields = hash key store in
  let count = if Keys.mem field fields then "0" else "1" in
  Ok (count, save_hash key (Keys.add field value fields) store)
let hdel key field store = let* fields = hash key store in
  let count = if Keys.mem field fields then "1" else "0" in
  Ok (count, save_hash key (Keys.remove field fields) store)
let hincrby key field amount store =
  let* amount = integer amount in let* old = hget key field store in
  let* value = integer (Option.value ~default:"0" old) |> Result.map_error (fun _ -> Hash_not_integer) in
  let* text = add value amount in let* _count, after = hset key field text store in Ok (text, after)
let members key store = Keys.find_opt key store |> Option.fold ~none:(Ok Members.empty) ~some:(function
  | Set values -> Ok (Members.of_list values)
  | Str _ | Hash _ | List _ | ZSet _ | Stream _ -> Error Wrong_type)
let save_set key values store =
  if Members.is_empty values then Keys.remove key store else put key (Set (Members.elements values)) store
let sismember key member store = let* values = members key store in
  Ok (if Members.mem member values then "1" else "0")
let scard key store = let* values = members key store in Ok (string_of_int (Members.cardinal values))
let sadd key member store = let* values = members key store in
  if Members.mem member values then Ok ("0", store)
  else Ok ("1", save_set key (Members.add member values) store)
let srem key member store = let* values = members key store in
  if Members.mem member values then Ok ("1", save_set key (Members.remove member values) store)
  else Ok ("0", store)
