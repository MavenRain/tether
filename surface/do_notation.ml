module T = Kanon_surface.Token
module L = Kanon_surface.Lexer
let ( let* ) = Result.bind

type token = Base of T.t | Open of T.loc | Close of T.loc
           | Semi of T.loc | Bind of T.loc

let error loc message = Error (Diagnostic.Syntax
  (Printf.sprintf "DO-SYNTAX %d:%d %s" loc.T.line loc.T.col message))
let tokens loc kinds = List.map (fun kind -> { T.kind; loc }) kinds
let parens loc body = tokens loc [T.LParen] @ body @ tokens loc [T.RParen]

(* Delegate ordinary source spans and byte decoding to the pinned lexer.
   Only the four new punctuation tokens are interpreted here. Locations
   retain their original line and column even after a span boundary. *)
let lex source =
  let flush start pending acc =
    let* ts = L.go start (List.rev pending) []
      |> Result.map_error (fun e -> Diagnostic.Kernel e) in
    Ok (List.fold_left (fun acc (t : T.t) ->
      if t.kind = T.Eof then acc else Base t :: acc) acc ts) in
  let rec comment loc = function
    | [] -> loc, []
    | '\n' :: rest -> T.next_line loc, rest
    | _c :: rest -> comment (T.next_col loc) rest in
  let rec scan start loc pending acc = function
    | [] ->
        let* acc = flush start pending acc in
        Ok (List.rev (Base { T.kind = T.Eof; loc } :: acc))
    | 'b' :: '"' :: rest ->
        let* acc = flush start pending acc in
        let* bytes, next, rest = L.byte_literal (T.advance loc 2) rest []
          |> Result.map_error (fun e -> Diagnostic.Kernel e) in
        scan next next [] (Base { T.kind = T.Bytes bytes; loc } :: acc) rest
    | '-' :: '-' :: rest ->
        let* acc = flush start pending acc in
        let next, rest = comment (T.advance loc 2) rest in
        scan next next [] acc rest
    | '<' :: '-' :: rest -> special start loc pending acc (Bind loc) 2 rest
    | '{' :: rest -> special start loc pending acc (Open loc) 1 rest
    | '}' :: rest -> special start loc pending acc (Close loc) 1 rest
    | ';' :: rest -> special start loc pending acc (Semi loc) 1 rest
    | c :: rest when L.is_ident_start c ->
        let chars, next, rest = L.span L.is_ident_char (T.next_col loc) rest in
        scan start next (List.rev_append (c :: chars) pending) acc rest
    | c :: rest ->
        let next = if c = '\n' then T.next_line loc else T.next_col loc in
        scan start next (c :: pending) acc rest
  and special start loc pending acc token width rest =
    let* acc = flush start pending acc in
    let next = T.advance loc width in
    scan next next [] (token :: acc) rest in
  scan T.start T.start [] [] (String.to_seq source |> List.of_seq)

(* A bind appends the existing Reply continuation. The command expression
   stays outside its binder, and no fresh term names are introduced. The
   kernel checks command arity, the Script tag and the Client result type. *)
let expand input =
  let rec walk acc = function
    | Base { T.kind = T.Ident "do"; loc } :: Open _ :: rest ->
        let* body, rest = block loc rest in
        walk (List.rev_append (parens loc body) acc) rest
    | Base t :: rest -> walk (t :: acc) rest
    | (Open loc | Close loc | Semi loc | Bind loc) :: _rest ->
        error loc "punctuation outside a do block"
    | [] -> Ok (List.rev acc)
  and fragment start depth acc = function
    | Base { T.kind = T.Ident "do"; loc } :: Open _ :: rest ->
        let* body, rest = block loc rest in
        fragment start depth (List.rev_append (parens loc body) acc) rest
    | Base { T.kind = T.Eof; loc } :: _rest -> error loc "unclosed do block"
    | Base ({ T.kind = T.LParen; loc = _ } as t) :: rest ->
        fragment start (depth + 1) (t :: acc) rest
    | Base ({ T.kind = T.RParen; loc } as t) :: rest ->
        if depth = 0 then error loc "unmatched parenthesis in do block"
        else fragment start (depth - 1) (t :: acc) rest
    | ((Semi loc | Close loc) :: _rest) as tail ->
        if depth <> 0 then error loc "close parentheses before ending a do statement"
        else if acc = [] then error loc "expected a command or final expression"
        else Ok (List.rev acc, tail)
    | (Open loc | Bind loc) :: _rest -> error loc "expected name <- command; or a final expression"
    | Base t :: rest -> fragment start depth (t :: acc) rest
    | [] -> error start "unclosed do block"
  and block start = function
    | Base { T.kind = T.Ident name; loc } :: Bind _ :: rest ->
        let* action, rest = fragment start 0 [] rest in
        (match rest with
         | Semi _ :: rest ->
             let* body, rest = block start rest in
             let continuation = tokens loc
               [T.KFun; T.LParen; T.Ident name; T.Colon; T.Ident "Reply";
                T.RParen; T.DArrow] @ parens loc body in
             Ok (parens loc action @ parens loc continuation, rest)
         | Close loc :: _rest -> error loc "a bind needs ';' and a final expression"
         | Base _ :: _ | Open _ :: _ | Bind _ :: _ | [] -> error start "expected ';' after command")
    | rest ->
        let* final, rest = fragment start 0 [] rest in
        (match rest with
         | Close _ :: rest | Semi _ :: Close _ :: rest -> Ok (final, rest)
         | Semi loc :: _rest -> error loc "only a reply bind may precede the final expression"
         | Base _ :: _ | Open _ :: _ | Bind _ :: _ | [] -> error start "expected '}' after final expression") in
  walk [] input

let parse source = let* ts = lex source in expand ts
