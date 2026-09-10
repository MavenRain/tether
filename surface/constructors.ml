open Kanon_kernel
let ( let* ) = Result.bind
let prefix = "tetherCtor_"

(* The inherited elaborator cannot apply parameterized constructors.
   Ordinary checked functions expose their complete erased-parameter
   telescope. No family record or kernel rule changes. *)
let declaration (family : Positivity.family) (ctor : Positivity.ctor) =
  let np = List.length family.f_params in
  let na = List.length ctor.c_args in
  let tele = family.f_params @ ctor.c_args in
  let params = List.init np (fun i -> Term.Var (na + np - i - 1)) in
  let args = List.init na (fun i -> Term.Var (na - i - 1)) in
  let shape = Shape.SMu (family.f_name, ctor.c_res_idx) in
  let result = Term.Lan (shape, Term.Sec (Shape.SColl np, List.map Rules.leg_of params)) in
  let body = Term.In (shape, Term.ACtor ctor.c_name, args) in
  let ty = List.fold_right (fun (q, x, dom) cod -> Rules.arrow q x dom cod) tele result in
  let body = List.fold_right (fun (q, x, dom) body ->
    Term.Sec (Shape.SPi (q, x, dom), [{ Term.l_binders = [q, x]; l_body = body }])) tele body in
  { Check.d_name = prefix ^ ctor.c_name; d_kind = Check.Definition;
    d_ty = ty; d_body = Some body }

let install ~budget globals =
  let decls = Global.StringMap.bindings globals.Global.families
    |> List.concat_map (fun (_name, (f : Positivity.family)) ->
        if f.f_params = [] then [] else List.map (declaration f) f.f_ctors) in
  let* rows = Check.check_decls ~budget globals decls in
  let globals = List.fold_left (fun g (name, entry) -> Global.add name entry g) globals rows in
  Ok (globals, rows)

let aliases globals =
  Global.StringMap.bindings globals.Global.families
  |> List.concat_map (fun (_name, (f : Positivity.family)) ->
      if f.f_params = [] then [] else
      List.map (fun (c : Positivity.ctor) -> c.c_name, prefix ^ c.c_name) f.f_ctors)
