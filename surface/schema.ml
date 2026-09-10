module T = Kanon_surface.Token
let ( let* ) = Result.bind

type encoding = Binary | Int64
type redis_type = Str of encoding | Hash | List | Set | ZSet | Stream
type t = { name : string; redis_type : redis_type; tag : int list }

let type_text = function
  | Str Binary -> "(Str Binary)"
  | Str Int64 -> "(Str Int64)"
  | Hash -> "Hash"
  | List -> "List"
  | Set -> "Set"
  | ZSet -> "ZSet"
  | Stream -> "Stream"

let bytes s = List.of_seq (String.to_seq s) |> List.map Char.code
let valid_component bytes =
  bytes <> [] && List.for_all (fun c -> c <> 123 && c <> 125) bytes

let make name redis_type tag =
  if valid_component tag then Ok { name; redis_type; tag }
  else Error (Diagnostic.Schema (name ^ ": tag must be nonempty and contain no braces"))

let parse_type = function
  | { T.kind = T.LParen; loc = _ } :: { T.kind = T.Ident "Str"; loc = _ }
    :: { T.kind = T.Ident encoding; loc = _ } :: { T.kind = T.RParen; loc = _ } :: rest ->
      if String.equal encoding "Int64" then Ok (Str Int64, rest)
      else if String.equal encoding "Binary" then Ok (Str Binary, rest)
      else Error (Diagnostic.Syntax "Str requires Int64 or Binary")
  | { T.kind = T.Ident name; loc = _ } :: rest ->
      let* ty = match name with
        | "Hash" -> Ok Hash | "List" -> Ok List | "Set" -> Ok Set
        | "ZSet" -> Ok ZSet | "Stream" -> Ok Stream
        | s -> Error (Diagnostic.Syntax ("unknown Redis type " ^ s)) in
      Ok (ty, rest)
  | tokens -> Error (Diagnostic.Syntax
      ("expected a Redis type, remaining tokens=" ^ string_of_int (List.length tokens)))

let tokens loc kinds = List.map (fun kind -> { T.kind; loc }) kinds

let key s loc index =
  if not (valid_component index) then
    Error (Diagnostic.Schema (s.name ^ ": index must be nonempty and contain no braces"))
  else
    let* ty = Lexer.lex (type_text s.redis_type) in
    let ty = List.filter (fun (t : T.t) -> t.kind <> T.Eof) ty in
    let payload = [123] @ s.tag @ [125; 58] @ bytes s.name @ [58] @ index in
    Ok (tokens loc [T.LParen; T.Ident "keyBytes"] @ ty
        @ tokens loc [T.LParen; T.Ident "tag"; T.Bytes s.tag; T.RParen;
                       T.Bytes payload; T.RParen])

let signed64 loc payload =
  let negative, digits = match payload with
    | 45 :: rest -> true, rest | cs -> false, cs in
  let canonical = match digits with
    | [] -> false
    | 48 :: [] -> not negative
    | 48 :: _rest -> false
    | cs -> List.for_all (fun c -> c >= 48 && c <= 57) cs in
  let bound = bytes (if negative then "9223372036854775808" else "9223372036854775807") in
  let size = List.length digits in
  if canonical && (size < 19 || (size = 19 && compare digits bound <= 0)) then
    Ok (tokens loc [T.LParen; T.Ident "signed64Bytes"; T.Bytes payload; T.RParen])
  else Error (Diagnostic.Int64 "expected a canonical signed 64-bit decimal")

let rec expand schemas input =
  match input with
  | [] -> Ok []
  | { T.kind = T.Ident name; loc } :: rest ->
      if List.mem name ["keyBytes"; "signed64Bytes"] then Error (Diagnostic.Reserved name)
      else if String.equal name "int64" then (
        match rest with
        | { T.kind = T.Bytes bytes; loc = _ } :: tail ->
            let* value = signed64 loc bytes in
            let* tail = expand schemas tail in Ok (value @ tail)
        | ts -> Error (Diagnostic.Int64
            ("int64 requires a byte literal, remaining tokens=" ^ string_of_int (List.length ts))))
      else
        let* prefix, tail =
          List.find_opt (fun s -> String.equal s.name name) schemas
          |> Option.fold ~none:(Ok ([{ T.kind = T.Ident name; loc }], rest))
               ~some:(fun s -> match rest with
                 | { T.kind = T.Bytes index; loc = _ } :: tail ->
                     Result.map (fun value -> value, tail) (key s loc index)
                 | ts -> Error (Diagnostic.Schema
                     (name ^ ": write a literal index after the family name; remaining tokens="
                      ^ string_of_int (List.length ts)))) in
        let* tail = expand schemas tail in Ok (prefix @ tail)
  | token :: rest -> Result.map (fun tail -> token :: tail) (expand schemas rest)
