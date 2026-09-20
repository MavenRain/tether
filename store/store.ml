module Keys = Map.Make (String) module Members = Set.Make (String)
type data = Str of string | Hash of (string * string) list | List of string list
  | Set of string list | ZSet of (string * string) list | Stream of (string * string) list
type t = { values : data Keys.t; deadlines : int64 Keys.t; now : int64 }
type fault = Wrong_type | Not_integer | Hash_not_integer | Overflow | Missing_key | Index_range | Expire_range of string | Expire_reply | Remove_range
let empty = { values = Keys.empty; deadlines = Keys.empty; now = 0L } let put key value store = { store with values = Keys.add key value store.values }
let remove key store = { store with values = Keys.remove key store.values; deadlines = Keys.remove key store.deadlines }
let bindings store = Keys.bindings store.values let save key value ~empty store = if empty then remove key store else put key value store
let message = function
  | Wrong_type -> "WRONGTYPE Operation against a key holding the wrong kind of value"
  | Not_integer -> "ERR value is not an integer or out of range" | Hash_not_integer -> "ERR hash value is not an integer"
  | Overflow -> "ERR increment or decrement would overflow" | Missing_key -> "ERR no such key" | Index_range -> "ERR index out of range"
  | Expire_range command -> "ERR invalid expire time in '" ^ command ^ "' command"
  | Expire_reply -> "ERR expiry reply is outside exact integer range" | Remove_range -> "ERR value is out of range, value must between -9223372036854775807 and 9223372036854775807"
let read empty project key store = Keys.find_opt key store.values |> Option.fold ~none:(Ok empty) ~some:project
let get = read None (function Str value -> Ok (Some value) | Hash _ | List _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
let integer text = Result.bind (Int64.of_string_opt text |> Option.to_result ~none:Not_integer) (fun value -> if Int64.to_string value = text then Ok value else Error Not_integer)
let set key value store = "OK", put key (Str value) (remove key store)
let exists key store = if Keys.mem key store.values then "1" else "0" let del key store = exists key store, remove key store
let ( let* ) = Result.bind
let add value amount = if (amount > 0L && value > Int64.sub Int64.max_int amount) || (amount < 0L && value < Int64.sub Int64.min_int amount) then Error Overflow
  else Ok (Int64.to_string (Int64.add value amount))
let incrby key amount store = let* amount = integer amount in let* value = get key store in
  let* value = integer (Option.value ~default:"0" value) in let* text = add value amount in Ok (text, put key (Str text) store)
let incr key store = incrby key "1" store let decr key store = incrby key "-1" store
let advance milliseconds store = let* delta = integer milliseconds in if delta < 0L then Error Not_integer else let* now = add store.now delta in let* now = integer now in
  Ok (Keys.fold (fun key deadline next -> if deadline < now then remove key next else next) store.deadlines { store with now })
type expiry_condition = NX | XX | GT | LT
let expire ?condition ?(absolute=false) ~seconds key amount store = let* amount = integer amount in let range = Expire_range ((if seconds then "expire" else "pexpire") ^ (if absolute then "at" else "")) in
  if seconds && (amount > 9223372036854775L || amount < -9223372036854775L) then Error range else
  let* deadline = add (if absolute then 0L else store.now) (if seconds then Int64.mul amount 1000L else amount) |> Result.map_error (fun _ -> range) in
  let* deadline = integer deadline in let previous = Keys.find_opt key store.deadlines in
  let allowed = Option.fold ~none:true ~some:(function NX -> Option.is_none previous | XX -> Option.is_some previous
    | GT -> Option.fold ~none:false ~some:(fun old -> deadline > old) previous | LT -> Option.fold ~none:true ~some:(fun old -> deadline < old) previous) condition in
  if exists key store = "0" || not allowed then Ok ("0", store) else Ok ("1", if deadline <= store.now then remove key store else { store with deadlines = Keys.add key deadline store.deadlines })
let ttl ?(absolute=false) ~seconds key store = let remaining = Keys.find_opt key store.deadlines |> Option.map (fun t -> if absolute then t else Int64.sub t store.now) in
  let value = if exists key store = "0" then -2L else Option.fold ~none:(-1L) ~some:(fun ms -> if seconds then Int64.add (Int64.div ms 1000L) (if Int64.rem ms 1000L >= 500L then 1L else 0L) else ms) remaining in
  if value >= 9007199254740992L then Error Expire_reply else Ok (Int64.to_string value)
let persist key store = (if Keys.mem key store.deadlines then "1" else "0"), { store with deadlines = Keys.remove key store.deadlines }
let hash = read Keys.empty (function Hash fields -> Ok (Keys.of_seq (List.to_seq fields)) | Str _ | List _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
let save_hash key fields store = save key (Hash (Keys.bindings fields)) ~empty:(Keys.is_empty fields) store
let hget key field store = let* fields = hash key store in Ok (Keys.find_opt field fields)
let hmget key first rest store = let* fields = hash key store in Ok (List.map (fun field -> Keys.find_opt field fields) (first :: rest))
let hexists key field store = let* fields = hash key store in Ok (if Keys.mem field fields then "1" else "0")
let hlen key store = let* fields = hash key store in Ok (string_of_int (Keys.cardinal fields)) let hstrlen key field store = Result.map (fun value -> string_of_int (Option.fold ~none:0 ~some:String.length value)) (hget key field store)
let hgetall key store = Result.map (fun fields -> List.concat_map (fun (f, v) -> [f; v]) (Keys.bindings fields)) (hash key store)
let hproject project key store = Result.map (fun fs -> List.sort String.compare (List.map project (Keys.bindings fs))) (hash key store)
let hset ?(nx = false) ?(rest = []) key field value store = let* fields = hash key store in if nx && List.exists (fun (f, _) -> Keys.mem f fields) ((field, value) :: rest) then Ok ("0", store) else let updated = List.fold_left (fun acc (f, v) -> Keys.add f v acc) (Keys.add field value fields) rest in Ok (string_of_int (match () with () when nx -> 1 | () -> Keys.cardinal updated - Keys.cardinal fields), save_hash key updated store)
let hdel ?(rest = []) key field store = let* fields = hash key store in
  let next = List.fold_left (fun acc name -> Keys.remove name acc) (Keys.remove field fields) rest in Ok (string_of_int (Keys.cardinal fields - Keys.cardinal next), save_hash key next store)
let hincrby key field amount store = let* amount = integer amount in let* old = hget key field store in
  let* value = integer (Option.value ~default:"0" old) |> Result.map_error (fun _ -> Hash_not_integer) in
  let* text = add value amount in let* _count, after = hset key field text store in Ok (text, after)
let members = read Members.empty (function Set values -> Ok (Members.of_list values) | Str _ | Hash _ | List _ | ZSet _ | Stream _ -> Error Wrong_type)
let save_set key values store = save key (Set (Members.elements values)) ~empty:(Members.is_empty values) store
let sismember key member store = Result.map (fun values -> if Members.mem member values then "1" else "0") (members key store)
let scard key store = let* values = members key store in Ok (string_of_int (Members.cardinal values)) let smembers key store = Result.map Members.elements (members key store)
let scombine op key other store = let* left = members key store in let* right = members other store in Ok (Members.elements (op left right))
let sstore op destination key other store = let* values = scombine op key other store in Ok (string_of_int (List.length values), save destination (Set values) ~empty:(values = []) (remove destination store))
let change_set ?(rest = []) update key member store = let* values = members key store in let next = List.fold_left (fun acc item -> update item acc) (update member values) rest in
  if Members.equal values next then Ok ("0", store) else Ok (string_of_int (abs (Members.cardinal next - Members.cardinal values)), save_set key next store)
let sadd = change_set Members.add let srem = change_set Members.remove
let smove key other member store = let* present = sismember key member store in let* _ = if Keys.mem key store.values then members other store else Ok Members.empty in
  if present = "0" || key = other then Ok (present, store) else let* _, next = srem key member store in Result.map (fun (_, after) -> "1", after) (sadd other member next)
let list = read [] (function List values -> Ok values | Str _ | Hash _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
type side = Left | Right let orient = function Left -> Fun.id | Right -> List.rev
let llen key store = let* values = list key store in Ok (string_of_int (List.length values))
let push ?(xx = false) ?(rest = []) side key value store = let* values = list key store in if xx && values = [] then Ok ("0", store) else let values = orient side (List.rev_append rest (value :: orient side values)) in Ok (string_of_int (List.length values), put key (List values) store)
let pop side key store = let* values = list key store in match orient side values with | [] -> Ok (None, store)
  | value :: rest -> Ok (Some value, save key (List (orient side rest)) ~empty:(rest = []) store)
let position values index = if index < 0L then Int64.add (Int64.of_int (List.length values)) index else index let indexed values = List.mapi (fun i v -> Int64.of_int i, v) values
let lindex key index store = let* values = list key store in if values = [] then Ok None else let* index = integer index in Ok (List.assoc_opt (position values index) (indexed values))
let lset key index value store = let* values = list key store in if values = [] then Error Missing_key else let* index = integer index in let index = position values index in
  if index < 0L || index >= Int64.of_int (List.length values) then Error Index_range else
  Ok ("OK", put key (List (List.mapi (fun i v -> if Int64.of_int i = index then value else v) values)) store)
let lrange key first last store = let* first = integer first in let* last = integer last in let* values = list key store in let first, last = position values first, position values last in
  Ok (List.filter_map (fun (i, v) -> if i >= first && i <= last then Some v else None) (indexed values))
let ltrim key first last store = let* values = lrange key first last store in Ok ("OK", save key (List values) ~empty:(values = []) store)
let lrem key count value store = let* count = integer count in if count = Int64.min_int then Error Remove_range else let* values = list key store in let side = if count < 0L then Right else Left in
  let removed, kept = List.fold_left (fun (n, kept) v -> if v = value && (count = 0L || (if count < 0L then Int64.neg n > count else n < count)) then Int64.succ n, kept else n, v :: kept) (0L, []) (orient side values) in
  Ok (Int64.to_string removed, save key (List (orient side (List.rev kept))) ~empty:(kept = []) store)
