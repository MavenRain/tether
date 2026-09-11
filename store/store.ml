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
let incr key store =
  Result.bind (get key store) (fun value ->
  Result.bind (integer (Option.value ~default:"0" value)) (fun value ->
    if value = Int64.max_int then Error Overflow else
    let text = Int64.to_string (Int64.succ value) in
    Ok (text, put key (Str text) store)))
