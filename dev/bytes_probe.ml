module K = Kanon_kernel
module P = Tether_print
let ( let* ) = Result.bind
let read path =
  print_endline ("READ " ^ path); flush stdout;
  let* line = In_channel.input_line stdin |> Option.to_result ~none:(K.Error.Mismatch "input") in
  let* size = int_of_string_opt line |> Option.to_result ~none:(K.Error.Mismatch "length") in
  if size < 0 || size > 1048576 then Error (K.Error.Mismatch "size") else
  In_channel.really_input_string stdin size |> Option.to_result ~none:(K.Error.Mismatch "data")
let run () =
  let budget = K.Budget.unlimited in
  let* reactor = read "@reactor" in let* sample = read "Bytes.bin" in
  let* reference = P.Transport.wasm ~budget ~reactor
    { P.Lua.body = sample; sha1 = ""; no_writes = true; keys = [] } in
  let* globals, rows = Kanon_surface.Elab.check_in ~budget K.Global.initial
    (reactor ^ "\ndef requestBody : Bytes := bytesNil\n") in
  let* rows = K.Erase.program ~budget globals rows in
  let* rows = P.Transport.byte_constants ["requestBody", sample] rows in
  let* lowered = Kanon_wasm.Emit.reactor rows
    ~exports:["requestBody"; "bytesEmpty"; "bytesHead"; "bytesTail"] in
  print_endline ("REFERENCE " ^ P.Transport.hex reference);
  print_endline ("LOWERED " ^ P.Transport.hex lowered); Ok ()
let () = run () |> Result.fold ~ok:Fun.id ~error:(fun e -> prerr_endline (K.Error.to_string e); exit 1)
