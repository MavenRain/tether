module Keys = Map.Make (String)
type data = Str of string | Hash of (string * string) list | List of string list
  | Set of string list | ZSet of (string * string) list | Stream of (string * string) list
type t = data Keys.t
type fault = Wrong_type | Not_integer | Overflow
let empty = Keys.empty
let put = Keys.add
let message = function
  | Wrong_type -> "WRONGTYPE Operation against a key holding the wrong kind of value"
  | Not_integer -> "ERR value is not an integer or out of range"
  | Overflow -> "ERR increment or decrement would overflow"
let get key store = Keys.find_opt key store |> Option.fold ~none:(Ok None) ~some:(function
  | Str value -> Ok (Some value)
  | Hash _ | List _ | Set _ | ZSet _ | Stream _ -> Error Wrong_type)
let integer text = Result.bind (Int64.of_string_opt text |> Option.to_result ~none:Not_integer)
  (fun value -> if Int64.to_string value = text then Ok value else Error Not_integer)
let set key value store = "OK", put key (Str value) store
let exists key store = if Keys.mem key store then "1" else "0"
let del key store = exists key store, Keys.remove key store
let incrby key amount store =
  Result.bind (integer amount) (fun amount ->
  Result.bind (get key store) (fun value ->
  Result.bind (integer (Option.value ~default:"0" value)) (fun value ->
    if (amount > 0L && value > Int64.sub Int64.max_int amount)
      || (amount < 0L && value < Int64.sub Int64.min_int amount) then Error Overflow else
    let text = Int64.to_string (Int64.add value amount) in
    Ok (text, put key (Str text) store))))
let incr key store = incrby key "1" store
let decr key store = incrby key "-1" store
