module Keys = Map.Make (String)
module Members = Set.Make (String)
type data = Str of string | Hash of (string * string) list | List of string list
  | Set of string list | ZSet of (string * string) list | Stream of (string * string) list
type t = data Keys.t
type fault = Wrong_type | Not_integer | Hash_not_integer | Overflow | Missing_key | Index_range
let empty = Keys.empty let put = Keys.add
let save key value ~empty store = if empty then Keys.remove key store else put key value store
let message = function
  | Wrong_type -> "WRONGTYPE Operation against a key holding the wrong kind of value"
  | Not_integer -> "ERR value is not an integer or out of range"
  | Hash_not_integer -> "ERR hash value is not an integer"
  | Overflow -> "ERR increment or decrement would overflow"
  | Missing_key -> "ERR no such key"
  | Index_range -> "ERR index out of range"
let get key store = Keys.find_opt key store |> Option.fold ~none:(Ok None) ~some:(function
  | Str value -> Ok (Some value) | Hash _ | List _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
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
let incr key store = incrby key "1" store let decr key store = incrby key "-1" store
let hash key store = Keys.find_opt key store |> Option.fold ~none:(Ok Keys.empty) ~some:(function
  | Hash fields -> Ok (Keys.of_seq (List.to_seq fields)) | Str _ | List _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
let save_hash key fields store = save key (Hash (Keys.bindings fields)) ~empty:(Keys.is_empty fields) store
let hget key field store = let* fields = hash key store in Ok (Keys.find_opt field fields)
let hexists key field store = let* fields = hash key store in Ok (if Keys.mem field fields then "1" else "0")
let hlen key store = let* fields = hash key store in Ok (string_of_int (Keys.cardinal fields))
let hgetall key store = Result.map (fun fields -> List.concat_map (fun (f, v) -> [f; v]) (Keys.bindings fields)) (hash key store)
let hproject project key store = Result.map (fun fs -> List.sort String.compare (List.map project (Keys.bindings fs))) (hash key store)
let change_hash ~adding update key field store = let* fields = hash key store in
  let count = if Keys.mem field fields = adding then "0" else "1" in
  Ok (count, save_hash key (update fields) store)
let hset key field value = change_hash ~adding:true (Keys.add field value) key field
let hdel key field = change_hash ~adding:false (Keys.remove field) key field
let hincrby key field amount store =
  let* amount = integer amount in let* old = hget key field store in
  let* value = integer (Option.value ~default:"0" old) |> Result.map_error (fun _ -> Hash_not_integer) in
  let* text = add value amount in let* _count, after = hset key field text store in Ok (text, after)
let members key store = Keys.find_opt key store |> Option.fold ~none:(Ok Members.empty) ~some:(function
  | Set values -> Ok (Members.of_list values) | Str _ | Hash _ | List _ | ZSet _ | Stream _ -> Error Wrong_type)
let save_set key values store = save key (Set (Members.elements values)) ~empty:(Members.is_empty values) store
let sismember key member store = Result.map (fun values -> if Members.mem member values then "1" else "0") (members key store)
let scard key store = let* values = members key store in Ok (string_of_int (Members.cardinal values))
let smembers key store = Result.map Members.elements (members key store)
let scombine op key other store = let* left = members key store in let* right = members other store in Ok (Members.elements (op left right))
let change_set update key member store = let* values = members key store in let next = update member values in
  if Members.equal values next then Ok ("0", store) else Ok ("1", save_set key next store)
let sadd = change_set Members.add let srem = change_set Members.remove
let list key store = Keys.find_opt key store |> Option.fold ~none:(Ok []) ~some:(function
  | List values -> Ok values | Str _ | Hash _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
type side = Left | Right
let orient = function Left -> Fun.id | Right -> List.rev
let llen key store = let* values = list key store in Ok (string_of_int (List.length values))
let push side key value store = let* values = list key store in
  let values = orient side (value :: orient side values) in
  Ok (string_of_int (List.length values), put key (List values) store)
let pop side key store = let* values = list key store in match orient side values with
  | [] -> Ok (None, store)
  | value :: rest -> Ok (Some value, save key (List (orient side rest)) ~empty:(rest = []) store)
let position values index = if index < 0L then Int64.add (Int64.of_int (List.length values)) index else index
let indexed values = List.mapi (fun i v -> Int64.of_int i, v) values
let lindex key index store = let* values = list key store in
  if values = [] then Ok None else let* index = integer index in
  Ok (List.assoc_opt (position values index) (indexed values))
let lset key index value store = let* values = list key store in
  if values = [] then Error Missing_key else let* index = integer index in let index = position values index in
  if index < 0L || index >= Int64.of_int (List.length values) then Error Index_range else
  Ok ("OK", put key (List (List.mapi (fun i v -> if Int64.of_int i = index then value else v) values)) store)
let lrange key first last store = let* first = integer first in let* last = integer last in
  let* values = list key store in let first, last = position values first, position values last in
  Ok (List.filter_map (fun (i, v) -> if i >= first && i <= last then Some v else None) (indexed values))
let ltrim key first last store = let* values = lrange key first last store in
  Ok ("OK", save key (List values) ~empty:(values = []) store)
