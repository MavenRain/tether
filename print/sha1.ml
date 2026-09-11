(* SHA-1 is the Redis script identifier, not a security authenticator. *)
module Words = Map.Make (Int)
let ( let* ) = Result.bind
let xor = Int32.logxor
let add = Int32.add
let rot n x = Int32.logor (Int32.shift_left x n) (Int32.shift_right_logical x (32 - n))
let word words i = Words.find_opt i words |> Option.to_result ~none:"SHA1-SCHEDULE"

let block state bytes =
  let _, _, words = List.fold_left (fun (i, value, words) byte ->
    let value = Int32.logor (Int32.shift_left value 8) (Int32.of_int byte) in
    if i land 3 = 3 then (i + 1, 0l, Words.add (i lsr 2) value words)
    else (i + 1, value, words)) (0, 0l, Words.empty) bytes in
  let* words = List.fold_left (fun acc i ->
    let* words = acc in
    let* a = word words (i - 3) in let* b = word words (i - 8) in
    let* c = word words (i - 14) in let* d = word words (i - 16) in
    Ok (Words.add i (rot 1 (xor (xor a b) (xor c d))) words))
    (Ok words) (List.init 64 (fun i -> i + 16)) in
  let* a, b, c, d, e = List.fold_left (fun acc i ->
    let* a, b, c, d, e = acc in
    let f, k = match () with
      | () when i < 20 ->
          (Int32.logor (Int32.logand b c) (Int32.logand (Int32.lognot b) d), 0x5a827999l)
      | () when i < 40 -> (xor (xor b c) d, 0x6ed9eba1l)
      | () when i < 60 ->
          (Int32.logor (Int32.logand b c) (Int32.logor (Int32.logand b d) (Int32.logand c d)), 0x8f1bbcdcl)
      | () -> (xor (xor b c) d, 0xca62c1d6l) in
    let* w = word words i in
    Ok (add (add (add (add (rot 5 a) f) e) k) w, a, rot 30 b, c, d))
    (Ok state) (List.init 80 Fun.id) in
  let h0, h1, h2, h3, h4 = state in
  Ok (add h0 a, add h1 b, add h2 c, add h3 d, add h4 e)

let digest text =
  let size = String.length text in
  let bits = Int64.shift_left (Int64.of_int size) 3 in
  let suffix = List.init 8 (fun i -> Int64.to_int
    (Int64.logand 255L (Int64.shift_right_logical bits ((7 - i) * 8)))) in
  let padding = 0x80 :: List.init ((55 - (size land 63)) land 63) (fun _i -> 0) in
  let bytes = List.of_seq (Seq.map Char.code (String.to_seq text)) @ padding @ suffix in
  let rec consume state pending size = function
    | [] -> if size = 0 then Ok state else Error "SHA1-BLOCK"
    | b :: rest ->
        if size = 63 then
          let* state = block state (List.rev (b :: pending)) in consume state [] 0 rest
        else consume state (b :: pending) (size + 1) rest in
  let* a, b, c, d, e = consume
    (0x67452301l, 0xefcdab89l, 0x98badcfel, 0x10325476l, 0xc3d2e1f0l) [] 0 bytes in
  Ok (Printf.sprintf "%08lx%08lx%08lx%08lx%08lx" a b c d e)
