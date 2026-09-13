module D = Tether_surface.Diagnostic
module K = Kanon_kernel
module I = Tether_store.Interp
let ( let* ) = Result.bind
let read path =
  print_endline ("READ " ^ path); flush stdout;
  let* header = In_channel.input_line stdin |> Option.to_result ~none:(D.Read path) in
  let* size = int_of_string_opt header |> Option.to_result ~none:(D.Read path) in
  if size < 0 || size > 1048576 then Error (D.Read path) else
  In_channel.really_input_string stdin size |> Option.to_result ~none:(D.Read path)
let kernel result = Result.map_error (fun e -> D.Kernel e) result
let hex text = String.concat "" (List.of_seq (Seq.map (fun c -> Printf.sprintf "%02x" (Char.code c)) (String.to_seq text)))
let rec encode = function
  | I.Nil -> "null"
  | I.Int s -> "int:" ^ hex s
  | I.Bulk s -> "bulk:" ^ hex s
  | I.Status s -> "status:" ^ hex s
  | I.Err s -> "error:" ^ hex s
  | I.Array rs -> "array:[" ^ String.concat "," (List.map encode rs) ^ "]"
let run path entry key initial fuel =
  let* fuel = int_of_string_opt fuel |> Option.to_result ~none:(D.Syntax "STORE-FUEL") in
  if fuel < 0 then Error (D.Syntax "STORE-FUEL") else
  let remaining = ref fuel in
  let budget = K.Budget.of_poll (fun () -> if !remaining = 0 then true else (decr remaining; false)) in
  let* reactor = read "@reactor" in let* redis = read "@redis" in
  let* checked = Tether_surface.Elab.check ~budget ~read ~path ~reactor ~redis in
  let reply = K.Term.Lan (K.Shape.SMu ("Reply", []), K.Term.Sec (K.Shape.SColl 0, [])) in
  let ty = K.Term.Lan (K.Shape.SMu ("Client", []), K.Term.Sec (K.Shape.SColl 1, [K.Rules.leg_of reply])) in
  let* _checked = kernel (K.Check.check_decls ~budget checked.globals [{ K.Check.d_name = "tetherStoreEntryCheck";
    d_kind = K.Check.Definition; d_ty = ty; d_body = Some (K.Term.Global entry) }]) in
  let* rows = kernel (K.Erase.program ~budget checked.globals checked.rows) in
  let seeded value = Ok (Tether_store.Store.put key value Tether_store.Store.empty) in
  let* store = match initial with
    | "@missing" -> Ok Tether_store.Store.empty
    | "@hash" -> seeded (Tether_store.Store.Hash ["f", "v"])
    | "@set" -> seeded (Tether_store.Store.Set ["m"])
    | "@zset" -> seeded (Tether_store.Store.ZSet ["m", "1"])
    | "@stream" -> seeded (Tether_store.Store.Stream [])
    | _ ->
      if String.starts_with ~prefix:"@" initial then Error (D.Syntax "STORE-SEED")
      else seeded (Tether_store.Store.Str initial) in
  let* answer, _store = I.run ~budget rows ~entry store |> Result.map_error (fun e -> D.Syntax e) in
  print_endline ("REPLY " ^ encode answer); Ok ()
let () = (match Array.to_list Sys.argv with
  | [_program; path; entry; key; initial; fuel] -> run path entry key initial fuel
  | [] | _ :: _ -> Error (D.Syntax "expected path, entry, key, initial and fuel"))
  |> Result.fold ~ok:Fun.id ~error:(fun e -> prerr_endline (D.to_string e); exit 4)
