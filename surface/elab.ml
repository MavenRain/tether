module G = Kanon_kernel.Global
module S = Kanon_surface.Syntax
module Names = G.StringMap
let ( let* ) = Result.bind

type checked = {
  globals : G.t;
  rows : (string * G.entry) list;
  schemas : Schema.t list;
  owners : string Names.t;
}

let names_of = function
  | S.DDef (name, _ty, _body) -> [name]
  | S.DAxiom (name, _ty) -> [name]
  | S.DRec defs -> List.map (fun (d : S.rec_def) -> d.rd_name) defs
  | S.DMu fams -> List.concat_map
      (fun (f : S.fam) -> f.fm_name :: List.map (fun (c : S.fam_ctor) -> c.fc_name) f.fm_ctors) fams

let reserve owner names owners =
  List.fold_left (fun acc name ->
    let* owners = acc in
    if Names.mem name owners || List.mem name ["int64"; "module"; "import"; "schema"]
       || String.starts_with ~prefix:Constructors.prefix name then
      Error (Diagnostic.Duplicate name)
    else Ok (Names.add name owner owners)) (Ok owners) names

let initial ~budget ~reactor ~redis =
  let* globals, rows = Kanon_surface.Elab.check_in ~budget G.initial (reactor ^ "\n" ^ redis)
    |> Result.map_error (fun e -> Diagnostic.Kernel e) in
  let* globals, wrappers = Constructors.install ~budget globals
    |> Result.map_error (fun e -> Diagnostic.Kernel e) in
  let rows = rows @ wrappers in
  let owners = Names.fold (fun name _entry owners -> Names.add name "prelude" owners)
    globals.entries Names.empty in
  let owners = Names.fold (fun name (f : Kanon_kernel.Positivity.family) owners ->
    List.fold_left (fun owners name -> Names.add name "prelude" owners)
      owners (name :: List.map (fun (c : Kanon_kernel.Positivity.ctor) -> c.c_name) f.f_ctors))
    globals.families owners in
  Ok { globals; rows; schemas = []; owners }

let merge left right =
  let* owners = Names.fold (fun name owner acc ->
    let* owners = acc in
    let same = Names.find_opt name owners
      |> Option.fold ~none:true ~some:(String.equal owner) in
    if same then Ok (Names.add name owner owners) else Error (Diagnostic.Duplicate name))
    right.owners (Ok left.owners) in
  let union a b = Names.union (fun _name value _other -> Some value) a b in
  let entries = union left.globals.entries right.globals.entries in
  let families = union left.globals.families right.globals.families in
  let schemas = left.schemas @ List.filter
    (fun (s : Schema.t) -> not (List.exists (fun (t : Schema.t) -> s.name = t.name) left.schemas)) right.schemas in
  let rows = left.rows @ List.filter
    (fun (name, _entry) -> not (List.mem_assoc name left.rows)) right.rows in
  Ok { globals = { G.entries; families }; rows; schemas; owners }

let check_unit ~observe ~budget base imported (unit : Parser.t) =
  let* env = List.fold_left (fun acc name ->
    let* env = acc in
    let* dependency = List.assoc_opt name imported
      |> Option.to_result ~none:(Diagnostic.Module_path ("missing import " ^ name)) in
    merge env dependency) (Ok base) unit.imports in
  let* owners = reserve unit.name (List.map (fun (s : Schema.t) -> s.name) unit.schemas) env.owners in
  let schemas = env.schemas @ unit.schemas in
  let* decls = Parser.declarations schemas unit.body in
  List.iter (fun d -> observe "reserve" (names_of d)) decls;
  let* owners = reserve unit.name (List.concat_map names_of decls) owners in
  (* Only prelude names and generated wrappers can be captured by an expansion.
     Imported user exports stay available as local binder names. *)
  let protected = List.map fst (Names.bindings base.owners) in
  List.iter (fun d -> observe "rewrite" (names_of d)) decls;
  let* decls = Rewrite.declarations protected (Constructors.aliases env.globals) decls in
  List.iter (fun d -> observe "elaborate" (names_of d)) decls;
  let* globals, rows = Kanon_surface.Elab.elab_program_in ~budget env.globals decls
    |> Result.map_error (fun e -> Diagnostic.Kernel e) in
  Ok { globals; rows = env.rows @ rows; schemas; owners }

let check_observed ~observe ~budget ~read ~path ~reactor ~redis =
  let* units = Resolver.load ~read ~path in
  let* base = initial ~budget ~reactor ~redis in
  let* checked = List.fold_left (fun acc (unit : Parser.t) ->
    let* checked = acc in
    let* output = check_unit ~observe ~budget base checked unit in
    Ok ((unit.name, output) :: checked)) (Ok []) units in
  match checked with
  | (_name, output) :: _rest -> Ok output
  | [] -> Error (Diagnostic.Module_path "no entry module")

let check = check_observed ~observe:(fun _stage _names -> ())
