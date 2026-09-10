module T = Kanon_surface.Token
let ( let* ) = Result.bind
type t = { name : string; imports : string list; schemas : Schema.t list; body : T.t list }

let rec dotted acc = function
  | { T.kind = T.Dot; loc = _ } :: { T.kind = T.Ident name; loc = _ } :: rest ->
      dotted (name :: acc) rest
  | rest ->
      let* name = Modpath.validate (String.concat "." (List.rev acc)) in
      Ok (name, rest)

let name = function
  | { T.kind = T.Ident n; loc = _ } :: rest -> dotted [n] rest
  | ts -> Error (Diagnostic.Syntax
      ("expected module name, remaining tokens=" ^ string_of_int (List.length ts)))

let upper_start text =
  String.to_seq text |> Seq.uncons
  |> Option.fold ~none:false ~some:(fun (c, _rest) -> c >= 'A' && c <= 'Z')

(* A header stands where a declaration starts, so the token before a header
   always ends a declaration.  None of these token kinds ends one: each of them
   requires an operand after it.  A header shape that follows one of them is an
   ordinary use of the word, "(schema key : Nat)" and "fun (import : Type 0 ->
   Nat) => import Nat" for example. *)
let opens_operand previous =
  Option.fold ~none:false
    ~some:(fun kind ->
      List.mem kind
        [T.LParen; T.Colon; T.ColonEq; T.Arrow; T.DArrow; T.Star; T.Comma; T.Pipe])
    previous

(* A header carries no terminator, so a header written after the first
   declaration is otherwise read as an application inside the preceding term and
   reaches the kernel under an unrelated reason.  Exactly these two shapes open
   a header: "import Name" with a module name, and "schema NAME :".  The walk
   passes either shape where an operand is required, so a local binder named
   "import" or "schema" stays usable after "(", ":", ":=", "->", "=>", "*", ","
   and "|".  The walk stays conservative after a name: there it refuses the two
   shapes, because the grammar carries no terminator that tells an argument
   apart from the next declaration. *)
let rec late_header previous = function
  | { T.kind = T.Ident "import"; loc = _ } :: { T.kind = T.Ident target; loc = _ } :: _rest
    when (not (opens_operand previous)) && upper_start target ->
      Error (Diagnostic.Syntax
        "import and schema headers must precede the first declaration")
  | { T.kind = T.Ident "schema"; loc = _ } :: { T.kind = T.Ident _family; loc = _ }
    :: { T.kind = T.Colon; loc = _ } :: _rest when not (opens_operand previous) ->
      Error (Diagnostic.Syntax
        "import and schema headers must precede the first declaration")
  | token :: rest -> late_header (Some token.T.kind) rest
  | [] -> Ok ()

let rec headers module_name imports schemas = function
  | { T.kind = T.Ident "import"; loc = _ } :: rest ->
      let* imported, rest = name rest in
      headers module_name (imported :: imports) schemas rest
  | { T.kind = T.Ident "schema"; loc = _ }
    :: { T.kind = T.Ident family; loc = _ } :: { T.kind = T.Colon; loc = _ }
    :: { T.kind = T.Ident "String"; loc = _ } :: { T.kind = T.Arrow; loc = _ }
    :: { T.kind = T.Ident "Key"; loc = _ } :: rest ->
      let* redis_type, rest = Schema.parse_type rest in
      (match rest with
       | { T.kind = T.Ident "tag"; loc = _ } :: { T.kind = T.Bytes tag; loc = _ } :: tail ->
           let* schema = Schema.make family redis_type tag in
           headers module_name imports (schema :: schemas) tail
       | ts -> Error (Diagnostic.Syntax
           ("schema requires tag followed by a byte literal, remaining tokens=" ^ string_of_int (List.length ts))))
  | body ->
      (* A header after the first declaration, or a schema whose shape misses
         the arm above, must not become term tokens and reach the kernel. *)
      let* () = late_header None body in
      Ok { name = module_name; imports = List.rev imports; schemas = List.rev schemas; body }

let parse source =
  let* ts = Lexer.lex source in
  match ts with
  | { T.kind = T.Ident "module"; loc = _ } :: rest ->
      let* module_name, rest = name rest in
      headers module_name [] [] rest
  | rest -> Error (Diagnostic.Syntax
      ("file must start with module NAME, remaining tokens=" ^ string_of_int (List.length rest)))

let declarations schemas body =
  let* expanded = Schema.expand schemas body in
  Kanon_surface.Parser.parse_decls expanded []
  |> Result.map_error (fun e -> Diagnostic.Kernel e)
