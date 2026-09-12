module D = Tether_surface.Diagnostic
let ( let* ) = Result.bind

let legacy source =
  let expected = Kanon_surface.Lexer.lex source
    |> Result.map_error (fun e -> D.Kernel e) in
  let actual = Tether_surface.Lexer.lex source in
  if expected = actual then Ok () else Error ("legacy lexer drift: " ^ source)

let syntax source =
  let* tokens = Tether_surface.Lexer.lex source |> Result.map_error D.to_string in
  Kanon_surface.Parser.parse_decls tokens []
    |> Result.map_error Kanon_kernel.Error.to_string

let equivalent (source, explicit) =
  let* left = syntax source in
  let* right = syntax explicit in
  if left = right then Ok () else Error ("continuation differs: " ^ source)

let all f = List.fold_left (fun acc x -> let* () = acc in f x) (Ok ())

let legacy_cases = [
  ""; " \t\r\n"; "-- do { ignored <- ; }\n";
  "def do : Nat := 3\ndef x : Nat := do";
  "fun (do : Nat) => do";
  "a1b' b\"do { r <- get; }\" -- punctuation in bytes\nnext";
  "b\"\\x00\\x7f\\\\\\\";{}<-\\n\"";
  "b\"\"b\"next\""; "123b\"bytes\"";
  "() ( ) : := -> => * , . .1 .2 .10 |";
  "def axiom fun inj of case match as return with tuple sum prod absurd";
  "Prop Type let in auto mu mutual end nu and rec";
  "natAdd natSub natMul natEq natLt name_2' 1234";
  "( -- comment\n )"; "ab\"invalid\""; "b\"\\q\"";
  "b\"unterminated"; "b\"raw\nnewline\""; "def x : Client Reply := @";
  "a -- comment\n b\"one\"\n-- another\n()";
]

let equivalent_cases = [
  ("def x : Client Reply := do { done Reply nil }", "def x : Client Reply := done Reply nil");
  ("def x : Client Reply := do { done Reply nil; }", "def x : Client Reply := done Reply nil");
  ("def x : Client Reply := do { r <- inv Reply g s; done Reply r }",
   "def x : Client Reply := (inv Reply g s) (fun (r : Reply) => done Reply r)");
  ("def x : Client Reply := do { first <- incr Reply g k; last <- get Reply Int64 g k; pure Reply g first }",
   "def x : Client Reply := (incr Reply g k) (fun (first : Reply) => (get Reply Int64 g k) (fun (last : Reply) => pure Reply g first))");
  ("def x : Client Reply := do { _ <- inv Reply g s; fail Reply Network }",
   "def x : Client Reply := (inv Reply g s) (fun (_ : Reply) => fail Reply Network)");
  ("def x : Client Reply := do { r <- inv Reply g (do { pure Reply g nil }); do { done Reply r } }",
   "def x : Client Reply := (inv Reply g (pure Reply g nil)) (fun (r : Reply) => done Reply r)");
  ("def x : Client Reply := do { r <- inv Reply g s; r <- inv Reply g (pure Reply g r); done Reply r }",
   "def x : Client Reply := (inv Reply g s) (fun (r : Reply) => (inv Reply g (pure Reply g r)) (fun (r : Reply) => done Reply r))");
  ("def x : Client Reply := do { let n : Nat := 0 in done Reply (bulk b\";{}<-\") }",
   "def x : Client Reply := let n : Nat := 0 in done Reply (bulk b\";{}<-\")");
]

let malformed = [
  "do {}"; "do {"; "do { r <- inv Reply g s }";
  "do { r <- inv Reply g s; }"; "do { r <- ; done Reply r }";
  "do { r <- inv Reply g s; done Reply r";
  "do { done Reply nil; done Reply nil }";
  "do { done Reply nil;; }"; "do { (done Reply nil }";
  "do { done Reply nil) }"; "do { (done Reply nil; ) }";
  "do { (r) <- inv Reply g s; done Reply r }";
  "do { { done Reply nil } }"; "r <- inv Reply g s";
  "{ done Reply nil }"; "done Reply nil;";
  (* Block punctuation outside a do block: the one documented divergence
     from the pinned lexer, which reported an unexpected character. *)
  "def x : Prop := Prop;"; "{"; "}"; "<-";
]

let refuse prefix source = Tether_surface.Lexer.lex source |> Result.fold
  ~ok:(fun _ -> Error ("malformed do accepted: " ^ source))
  ~error:(fun e -> if String.starts_with ~prefix (D.to_string e) then Ok ()
    else Error ("wrong diagnostic: " ^ D.to_string e))

let run () =
  let* () = all legacy legacy_cases in
  let* () = all equivalent equivalent_cases in
  let* () = all (refuse "SYNTAX DO-SYNTAX ") malformed in
  let* () = refuse "SYNTAX DO-SYNTAX 3:7 " "-- line one\n do {\n r <- ;\n}" in
  Printf.printf "PASS DO-SYNTAX legacy=%d expansion=%d refusals=%d locations=1\n"
    (List.length legacy_cases) (List.length equivalent_cases) (List.length malformed);
  Ok ()

let () = Result.fold ~ok:Fun.id
  ~error:(fun message -> prerr_endline ("FAIL DO-SYNTAX " ^ message); exit 1) (run ())
