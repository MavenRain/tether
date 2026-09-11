(* Binary stdin permits the standard padding and binary test vectors. *)
let () =
  In_channel.input_all stdin |> Tether_print.Sha1.digest
  |> Result.fold ~ok:print_endline ~error:(fun error -> prerr_endline error; exit 1)
