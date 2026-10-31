"""Bounded, source-bound load arithmetic and independent static model diagnostics.

No solver, code execution, regional lookup or normative factor selection.  A
diagnostic comparison establishes only the supplied arithmetic predicate.
"""
from copy import deepcopy
from datetime import date
from decimal import Context, Decimal, InvalidOperation, localcontext
from fractions import Fraction
import re

FUNCTIONS = ("loads", "fe_model")
D = Decimal
ZERO = D(0)
NUMBER = re.compile(r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\Z")
COMPONENTS = ("FX", "FY", "FZ", "MX", "MY", "MZ")
DOFS = ("UX", "UY", "UZ", "RX", "RY", "RZ")
LOAD_UNITS = ("kPa", "kN/m", "kN", "kN*m")
QUANTITY_UNITS = ("kN/m", "kN*m2", "kN", "kN*m", "kN/m3", "MPa", "m2", "m4")


def quotient(numerator, denominator):
    """Keep terminating decimals exact; report repeating ratios at 180 digits.

    At most eight bounded inputs are multiplied in loads.  The enclosing
    2400-digit context also preserves cancellation between opposite extremes.
    A repeating division is a final reported quantity, never a load factor.
    """
    fraction = Fraction(numerator) / Fraction(denominator)
    remaining = fraction.denominator
    for prime in (2, 5):
        while remaining % prime == 0:
            remaining //= prime
    if remaining == 1:
        return numerator / denominator
    with localcontext(Context(prec=180)):
        return numerator / denominator


def fail(path, reason):
    raise ValueError(path + ":" + reason)


def obj(value, path, required=(), optional=()):
    if type(value) is not dict or set(value) - set(required) - set(optional) or set(required) - set(value):
        fail(path, "object_keys")
    return value


def text(value, path, maximum=2000):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        fail(path, "text")
    return value


def enum(value, path, options):
    text(value, path, 200)
    if value not in options:
        fail(path, "choice")
    return value


def seq(value, path, minimum, maximum):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        fail(path, "array_size")
    return value


def distinct_texts(value, path, minimum, maximum, options=None):
    result = [text(v, path + "/" + str(i), 200) for i, v in enumerate(seq(value, path, minimum, maximum))]
    if len(set(result)) != len(result) or options is not None and any(v not in options for v in result):
        fail(path, "duplicate_or_choice")
    return result


def iso(value, path):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail(path, "ISO_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail(path, "ISO_date")


def exact(value):
    if isinstance(value, D):
        if not value.is_finite():
            fail("output", "nonfinite")
        return "0" if value == 0 else str(value)
    if type(value) is dict:
        return {k: exact(v) for k, v in value.items()}
    if type(value) in (list, tuple):
        return [exact(v) for v in value]
    return value


class Read:
    def __init__(self, data):
        if type(data) is not dict:
            fail("data", "object")
        self.data = data
        self.as_of = iso(data.get("as_of"), "/as_of")
        enum(data.get("jurisdiction"), "/jurisdiction", ("RU",))
        self.units = {}
        self.texts = {}

    def n(self, value, path, unit, low=-D("1e100"), high=D("1e100"), integer=False):
        if type(value) not in (str, int) or len(str(value)) > 150 or not NUMBER.fullmatch(str(value)):
            fail(path, "exact_decimal_string_or_integer")
        try:
            number = D(value)
        except InvalidOperation:
            fail(path, "decimal")
        # Decimal abs/normalization obeys the active Emax and may overflow even
        # before an out-of-range literal can be rejected. Inspect raw metadata
        # and use context-free copy_abs before any arithmetic or normalization.
        if not number.is_finite() or len(number.as_tuple().digits) > 40 or abs(number.as_tuple().exponent) > 140:
            fail(path, "decimal_bounds")
        if number and (not -100 <= number.adjusted() <= 100 or not D("1e-100") <= number.copy_abs() <= D("1e100")):
            fail(path, "decimal_bounds")
        if not low <= number <= high or integer and number != number.to_integral_value():
            fail(path, "range_or_integer")
        self.units[path] = {"unit": unit, "not_after": self.as_of.isoformat()}
        return number

    def ref(self, item, path):
        return text(item.get("source_reference"), path + "/source_reference", 200)

    def observed(self, item, path, paths):
        """An optional actual record date is distinct from the analysis cutoff."""
        if "reference_date" in item:
            observed = iso(item["reference_date"], path + "/reference_date")
            if observed > self.as_of:
                fail(path, "future_record_date")
            for numeric_path in paths:
                self.units[numeric_path]["effective_date"] = observed.isoformat()
            return observed.isoformat()
        return None

    def standards(self, value):
        result = []
        ids = set()
        for i, item in enumerate(seq(value, "/standards", 0, 4)):
            path = "/standards/" + str(i)
            obj(item, path, ("document_identity", "edition", "publication_date", "effective_from", "effective_to", "source_reference"), ("excerpt",))
            identity = text(item["document_identity"], path + "/document_identity")
            text(item["edition"], path + "/edition")
            if (identity, item["edition"]) in ids:
                fail(path, "duplicate_edition")
            ids.add((identity, item["edition"]))
            published = iso(item["publication_date"], path + "/publication_date")
            start = iso(item["effective_from"], path + "/effective_from")
            end = iso(item["effective_to"], path + "/effective_to") if item["effective_to"] is not None else None
            if published > self.as_of or start > self.as_of or end is not None and (end < start or self.as_of > end):
                fail(path, "selected_edition_window")
            self.ref(item, path)
            if "excerpt" in item:
                self.texts[path + "/excerpt"] = text(item["excerpt"], path + "/excerpt", 6000)
            result.append(deepcopy(item))
        return result


def common(data, read, required, optional=()):
    obj(data, "data", ("as_of", "jurisdiction") + tuple(required), tuple(optional))
    return {"as_of": read.as_of.isoformat(), "jurisdiction": "RU", "draft_only": True,
            "normative_applicability_established": False, "model_certified": False}


def loads(data, r):
    out = common(data, r, ("site", "structure_class", "purpose", "standards", "actions", "combinations"))
    site = obj(data["site"], "/site", ("address_or_region", "snow_region", "wind_region", "ice_region", "terrain", "seismicity_description", "source_reference"))
    for key, value in site.items():
        text(value, "/site/" + key)
    structure_class = enum(data["structure_class"], "/structure_class", ("KS-1", "KS-2", "KS-3"))
    purpose = text(data["purpose"], "/purpose")
    standards = r.standards(data["standards"])
    table, by_id = [], {}
    for i, item in enumerate(seq(data["actions"], "/actions", 1, 12)):
        p = "/actions/" + str(i)
        obj(item, p, ("id", "name", "kind", "origin", "basis", "unit", "component", "scope_id", "exclusive_group", "source_reference", "parameters"), ("reference_date",))
        identity = text(item["id"], p + "/id", 100)
        if identity in by_id:
            fail(p, "duplicate_action")
        name = text(item["name"], p + "/name")
        kind = enum(item["kind"], p + "/kind", ("permanent", "long", "short", "special"))
        origin = enum(item["origin"], p + "/origin", ("gravity", "occupancy", "technology", "snow", "wind", "ice", "seismic", "other"))
        basis = enum(item["basis"], p + "/basis", ("direct", "layer", "snow", "wind_mean_selected_multiplier"))
        unit = enum(item["unit"], p + "/unit", LOAD_UNITS)
        component = enum(item["component"], p + "/component", COMPONENTS)
        if unit == "kN*m" and component not in COMPONENTS[3:] or unit != "kN*m" and component not in COMPONENTS[:3]:
            fail(p, "unit_component")
        scope_id = text(item["scope_id"], p + "/scope_id", 100)
        exclusive = None if item["exclusive_group"] is None else text(item["exclusive_group"], p + "/exclusive_group", 100)
        source = r.ref(item, p)
        parameters = item["parameters"]
        q = p + "/parameters"
        if basis == "direct":
            obj(parameters, q, ("value",))
            value = r.n(parameters["value"], q + "/value", unit)
            formula = "provided_signed_value"
        elif basis == "layer":
            obj(parameters, q, ("thickness_m", "specific_weight_kN_m3", "direction_sign"))
            if origin != "gravity" or kind != "permanent" or unit != "kPa":
                fail(p, "layer_scope")
            thickness = r.n(parameters["thickness_m"], q + "/thickness_m", "m", ZERO)
            weight = r.n(parameters["specific_weight_kN_m3"], q + "/specific_weight_kN_m3", "kN/m3", ZERO)
            sign = r.n(parameters["direction_sign"], q + "/direction_sign", "1", -D(1), D(1))
            if sign not in (-1, 1):
                fail(q, "direction_sign_plus_or_minus_one")
            value = thickness * weight * sign
            formula = "thickness_m * specific_weight_kN_m3 * direction_sign"
        elif basis == "snow":
            obj(parameters, q, ("ground_snow_kPa", "shape_coefficient", "exposure_coefficient", "thermal_coefficient", "direction_sign"))
            if origin != "snow" or unit != "kPa":
                fail(p, "snow_scope")
            value = D(1)
            for key in ("ground_snow_kPa", "shape_coefficient", "exposure_coefficient", "thermal_coefficient"):
                value *= r.n(parameters[key], q + "/" + key, "kPa" if key == "ground_snow_kPa" else "1", ZERO)
            sign = r.n(parameters["direction_sign"], q + "/direction_sign", "1", -D(1), D(1))
            if sign not in (-1, 1):
                fail(q, "direction_sign_plus_or_minus_one")
            value *= sign
            formula = "ground_snow_kPa * shape_coefficient * exposure_coefficient * thermal_coefficient * direction_sign"
        else:
            obj(parameters, q, ("base_pressure_kPa", "height_coefficient", "aerodynamic_coefficient", "selected_effective_multiplier", "multiplier_basis"))
            if origin != "wind" or unit != "kPa":
                fail(p, "wind_scope")
            base = r.n(parameters["base_pressure_kPa"], q + "/base_pressure_kPa", "kPa", ZERO)
            height = r.n(parameters["height_coefficient"], q + "/height_coefficient", "1", ZERO)
            aero = r.n(parameters["aerodynamic_coefficient"], q + "/aerodynamic_coefficient", "1")
            multiplier = r.n(parameters["selected_effective_multiplier"], q + "/selected_effective_multiplier", "1", ZERO)
            text(parameters["multiplier_basis"], q + "/multiplier_basis")
            value = base * height * aero * multiplier
            formula = "base_pressure_kPa * height_coefficient * aerodynamic_coefficient * selected_effective_multiplier"
        record = dict(id=identity, name=name, kind=kind, origin=origin, basis=basis, unit=unit, component=component,
                      scope_id=scope_id, exclusive_group=exclusive, normative_value=value, source_reference=source,
                      derivation=dict(formula=formula, parameters=deepcopy(parameters)))
        observed = r.observed(item,p,[v for v in r.units if v.startswith(q+"/")])
        if observed is not None:record["reference_date"]=observed
        by_id[identity] = record
        table.append(record)
    combinations, combination_ids, used, envelopes = [], set(), set(), {}
    for i, item in enumerate(seq(data["combinations"], "/combinations", 1, 12)):
        p = "/combinations/" + str(i)
        obj(item, p, ("id", "type", "limit_state", "leading_action_id", "gamma_n", "source_reference", "selection_basis", "terms"))
        identity = text(item["id"], p + "/id", 100)
        if identity in combination_ids:
            fail(p, "duplicate_combination")
        combination_ids.add(identity)
        kind = enum(item["type"], p + "/type", ("basic", "special"))
        limit = enum(item["limit_state"], p + "/limit_state", ("ULS", "SLS"))
        source = r.ref(item, p)
        text(item["selection_basis"], p + "/selection_basis")
        gamma_n = r.n(item["gamma_n"], p + "/gamma_n", "1", D("1e-100"))
        leading = item["leading_action_id"]
        if leading is not None:
            text(leading, p + "/leading_action_id", 100)
        terms, totals, seen, groups, leaders, special = [], {}, set(), set(), [], []
        for j, term in enumerate(seq(item["terms"], p + "/terms", 1, 12)):
            q = p + "/terms/" + str(j)
            obj(term, q, ("action_id", "role", "gamma_f", "psi", "source_reference"))
            action_id = text(term["action_id"], q + "/action_id", 100)
            if action_id not in by_id or action_id in seen:
                fail(q, "unknown_or_duplicate_action")
            seen.add(action_id)
            used.add(action_id)
            action = by_id[action_id]
            role = enum(term["role"], q + "/role", ("permanent", "leading", "accompanying", "special"))
            if action["kind"] == "permanent" and role != "permanent" or role == "permanent" and action["kind"] != "permanent":
                fail(q, "permanent_role")
            if action["kind"] == "special" and role != "special" or role == "special" and action["kind"] != "special":
                fail(q, "special_role")
            if role == "leading": leaders.append(action_id)
            if role == "special": special.append(action_id)
            group = action["exclusive_group"]
            if group is not None:
                if group in groups: fail(q, "mutually_exclusive_actions")
                groups.add(group)
            gamma = r.n(term["gamma_f"], q + "/gamma_f", "1", ZERO)
            psi = r.n(term["psi"], q + "/psi", "1", ZERO)
            ref = r.ref(term, q)
            design = action["normative_value"] * gamma
            contribution = design * psi * gamma_n
            key = (action["scope_id"], action["unit"], action["component"])
            totals[key] = totals.get(key, ZERO) + contribution
            terms.append(dict(action_id=action_id, role=role, normative_value=action["normative_value"], gamma_f=gamma, psi=psi,
                              design_value=design, contribution=contribution, unit=action["unit"], component=action["component"],
                              scope_id=action["scope_id"], source_reference=ref))
        if leaders != ([] if leading is None else [leading]):
            fail(p, "leading_action_mismatch")
        if kind == "basic" and special or kind == "special" and len(special) != 1:
            fail(p, "special_combination_requires_exactly_one_special_action")
        variables = [v for v in seen if by_id[v]["kind"] in ("long", "short")]
        if kind == "basic" and variables and leading is None:
            fail(p, "explicit_leading_action_required")
        total_rows = []
        for key, value in sorted(totals.items()):
            scope, unit, component = key
            total_rows.append(dict(scope_id=scope, unit=unit, component=component, value=value))
            envkey = (kind, limit) + key
            envelopes.setdefault(envkey, []).append((value, identity))
        combinations.append(dict(id=identity, type=kind, limit_state=limit, leading_action_id=leading, gamma_n=gamma_n,
                                 selection_basis=item["selection_basis"], terms=terms, totals_by_scope=total_rows, source_reference=source))
    envelope_rows = []
    for key, values in sorted(envelopes.items()):
        low, high = min(v[0] for v in values), max(v[0] for v in values)
        envelope_rows.append(dict(type=key[0], limit_state=key[1], scope_id=key[2], unit=key[3], component=key[4],
                                  minimum=low, maximum=high, minimum_combination_ids=[i for v, i in values if v == low],
                                  maximum_combination_ids=[i for v, i in values if v == high]))
    gaps = ["selected_standard_chain_and_combination_completeness_not_established", "load_effect_envelope_is_not_member_response"]
    if not standards: gaps.append("selected_standard_metadata_not_provided")
    unused = sorted(set(by_id) - used)
    if unused: gaps.append("some_actions_not_in_selected_combinations")
    out.update(site=deepcopy(site), structure_class=structure_class, purpose=purpose, standards=standards, load_table=table,
               combinations=combinations, envelopes=envelope_rows, unused_action_ids=unused, evidence_gaps=gaps,
               snow_wind_regional_lookup_performed=False, special_action_generation_performed=False,
               combination_generation_performed=False, design_approval=False)
    return out


def vector(item, path, r, unit):
    obj(item, path, ("x", "y", "z"))
    return [r.n(item[k], path + "/" + k, unit) for k in ("x", "y", "z")]


def vecout(values):
    return dict(zip(("x", "y", "z"), values))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def beam(item, p, r):
    obj(item, p, ("model", "span_m", "uniform_load_kN_m", "EI_kN_m2", "load_axis", "source_reference"), ("observations", "reference_date"))
    enum(item["model"], p + "/model", ("simply_supported_prismatic_linear_Euler_Bernoulli_full_span_UDL",))
    axis = enum(item["load_axis"], p + "/load_axis", ("Y", "Z"))
    length = r.n(item["span_m"], p + "/span_m", "m", D("1e-100"))
    q = r.n(item["uniform_load_kN_m"], p + "/uniform_load_kN_m", "kN/m")
    ei = r.n(item["EI_kN_m2"], p + "/EI_kN_m2", "kN*m2", D("1e-100"))
    source = r.ref(item, p)
    reference_date = r.observed(item,p,[p+"/"+v for v in ("span_m","uniform_load_kN_m","EI_kN_m2")])
    reaction = -q * length / 2
    moment = -q * length**2 / 8
    displacement = quotient(5 * q * length**4, 384 * ei)
    comparisons = []
    values = dict(reaction_left_kN=reaction, reaction_right_kN=reaction, midspan_sagging_moment_kNm=moment, midspan_displacement_m=displacement)
    for i, obs in enumerate(seq(item.get("observations", []), p + "/observations", 0, 4)):
        path = p + "/observations/" + str(i)
        obj(obs, path, ("quantity", "value", "absolute_tolerance", "source_reference"), ("reference_date",))
        quantity = enum(obs["quantity"], path + "/quantity", tuple(values))
        unit = "kN" if "reaction" in quantity else "kN*m" if "moment" in quantity else "m"
        actual = r.n(obs["value"], path + "/value", unit)
        tol = r.n(obs["absolute_tolerance"], path + "/absolute_tolerance", unit, ZERO)
        difference = actual - values[quantity]
        comparisons.append(dict(quantity=quantity, observed_value=actual, analytical_value=values[quantity], difference=difference,
                                absolute_tolerance=tol, within_selected_tolerance=abs(difference) <= tol, unit=unit, source_reference=r.ref(obs, path)))
        observed=r.observed(obs,path,[path+"/value"])
        if observed is not None:comparisons[-1]["reference_date"]=observed
    if len({v["quantity"] for v in comparisons}) != len(comparisons): fail(p, "duplicate_beam_observation")
    result = dict(model=item["model"], span_m=length, uniform_load_kN_m=q, EI_kN_m2=ei, load_axis=axis,
                sign_convention="load_and_displacement_positive_along_selected_global_axis_reactions_opposite_sagging_positive_for_negative_load",
                total_applied_kN=q*length, **values, comparisons=comparisons, source_reference=source,
                applicability_established=False, shear_deformation_and_second_order_included=False)
    if reference_date is not None:result["reference_date"]=reference_date
    return result


def mesh(item, p, r):
    obj(item, p, ("metric", "comparison_basis", "source_reference", "runs", "tolerance_rule"), ("absolute_tolerance", "relative_tolerance", "relative_denominator_floor"))
    metric = obj(item["metric"], p + "/metric", ("name", "unit", "location", "component", "combination_id"))
    for key, value in metric.items():text(value, p + "/metric/" + key, 200)
    enum(metric["unit"], p + "/metric/unit", ("m", "mm", "kN", "kN*m", "MPa", "1"))
    basis = text(item["comparison_basis"], p + "/comparison_basis")
    source = r.ref(item, p)
    rule = enum(item["tolerance_rule"], p + "/tolerance_rule", ("absolute_only", "relative_only", "both", "either"))
    need_abs, need_rel = rule != "relative_only", rule != "absolute_only"
    if ("absolute_tolerance" in item) != need_abs or ("relative_tolerance" in item) != need_rel or ("relative_denominator_floor" in item) != need_rel:
        fail(p, "tolerance_fields_for_rule")
    absolute = r.n(item["absolute_tolerance"], p + "/absolute_tolerance", metric["unit"], ZERO) if need_abs else None
    relative = r.n(item["relative_tolerance"], p + "/relative_tolerance", "1", ZERO) if need_rel else None
    floor = r.n(item["relative_denominator_floor"], p + "/relative_denominator_floor", metric["unit"], D("1e-100")) if need_rel else None
    runs, steps, seen = [], [], set()
    for i, row in enumerate(seq(item["runs"], p + "/runs", 2, 5)):
        path = p + "/runs/" + str(i)
        obj(row, path, ("id", "characteristic_size_m", "element_count", "value", "source_reference"), ("reference_date",))
        identity = text(row["id"], path + "/id", 100)
        if identity in seen: fail(path, "duplicate_run")
        seen.add(identity)
        h = r.n(row["characteristic_size_m"], path + "/characteristic_size_m", "m", D("1e-100"))
        count = r.n(row["element_count"], path + "/element_count", "count", D(1), D("1e12"), True)
        value = r.n(row["value"], path + "/value", metric["unit"])
        run = dict(id=identity, characteristic_size_m=h, element_count=count, value=value, source_reference=r.ref(row, path))
        observed=r.observed(row,path,[path+"/"+v for v in ("characteristic_size_m","element_count","value")])
        if observed is not None:run["reference_date"]=observed
        if runs:
            prev = runs[-1]
            if h >= prev["characteristic_size_m"] or count <= prev["element_count"]: fail(path, "strictly_refining_mesh_required")
            delta = value - prev["value"]
            relative_delta = quotient(abs(delta), max(abs(value), floor)) if need_rel else None
            a = abs(delta) <= absolute if need_abs else None
            # Compare the exact finite numerator/denominator inequality. The
            # final reported repeating ratio may round to the threshold.
            b = abs(delta) <= relative * max(abs(value), floor) if need_rel else None
            within = a if rule == "absolute_only" else b if rule == "relative_only" else a and b if rule == "both" else a or b
            steps.append(dict(coarse_run_id=prev["id"], fine_run_id=identity, size_ratio=quotient(prev["characteristic_size_m"],h),
                              signed_change=delta, absolute_change=abs(delta), relative_change=relative_delta,
                              absolute_comparison=a, relative_comparison=b, within_selected_tolerance=within))
            if need_rel and (relative_delta <= relative) != b:
                steps[-1]["relative_comparison_operands"] = dict(absolute_change=abs(delta), denominator_scale=max(abs(value),floor),
                                                                 relative_tolerance=relative, threshold_product=relative*max(abs(value),floor))
        runs.append(run)
    return dict(metric=deepcopy(metric), comparison_basis=basis, source_reference=source, runs=runs, steps=steps,
                tolerance_rule=rule, absolute_tolerance=absolute, relative_tolerance=relative, relative_denominator_floor=floor,
                last_change_within_selected_tolerance=steps[-1]["within_selected_tolerance"],
                last_change_not_larger_than_previous=None if len(steps)<2 else steps[-1]["absolute_change"]<=steps[-2]["absolute_change"],
                asymptotic_convergence_or_error_bound_established=False)


def model_review(item, p, r):
    obj(item, p, ("program", "version", "description", "axes_description", "axes_basis", "topology_scope", "foundation_model", "boundary_conditions", "source_reference",
                  "nodes", "elements", "supports", "stiffness_records", "coordinate_tolerance_m", "equilibrium_cases"), ("mesh_study", "reference_date"))
    context = {key:text(item[key], p + "/" + key) for key in ("program", "version", "description", "axes_description", "foundation_model", "boundary_conditions")}
    context["source_reference"] = r.ref(item, p)
    context["axes_basis"] = enum(item["axes_basis"],p+"/axes_basis",("right_handed_global_cartesian_m_kN_kNm",))
    context["topology_scope"] = enum(item["topology_scope"],p+"/topology_scope",("full_exported_model","selected_submodel"))
    tolerance = r.n(item["coordinate_tolerance_m"], p + "/coordinate_tolerance_m", "m", ZERO)
    nodes, node_rows = {}, []
    for i, row in enumerate(seq(item["nodes"], p + "/nodes", 1, 16)):
        q = p + "/nodes/" + str(i)
        obj(row, q, ("id", "position_m", "source_reference"))
        identity = text(row["id"], q + "/id", 100)
        if identity in nodes: fail(q, "duplicate_node")
        nodes[identity] = vector(row["position_m"], q + "/position_m", r, "m")
        node_rows.append(dict(id=identity, position_m=vecout(nodes[identity]), source_reference=r.ref(row, q)))
    edges = {key:set() for key in nodes}
    node_use, elements, element_ids, unknown_nodes, zero_extent = set(), [], set(), [], []
    for i, row in enumerate(seq(item["elements"], p + "/elements", 0, 16)):
        q = p + "/elements/" + str(i)
        obj(row, q, ("id", "type", "node_ids", "source_reference"))
        identity = text(row["id"], q + "/id", 100)
        if identity in element_ids: fail(q, "duplicate_element")
        element_ids.add(identity)
        typ = enum(row["type"], q + "/type", ("beam", "truss", "spring", "shell", "solid", "other"))
        ids = distinct_texts(row["node_ids"], q + "/node_ids", 2, 8)
        if typ in ("beam", "truss", "spring") and len(ids)!=2:fail(q,"two_node_element_required")
        missing = [v for v in ids if v not in nodes]
        if missing: unknown_nodes.append(dict(element_id=identity, unknown_node_ids=missing))
        known = [v for v in ids if v in nodes]
        node_use.update(known)
        for a in known:edges[a].update(v for v in known if v!=a)
        if len(known)==len(ids) and all(sum((x-y)**2 for x,y in zip(nodes[ids[0]],nodes[v]))<=tolerance**2 for v in ids[1:]):zero_extent.append(identity)
        elements.append(dict(id=identity, type=typ, node_ids=ids, source_reference=r.ref(row,q)))
    supports, support_lookup = [], {}
    for i,row in enumerate(seq(item["supports"],p+"/supports",0,16)):
        q=p+"/supports/"+str(i)
        obj(row,q,("node_id","restrained_dofs","compression_positive_direction","source_reference"))
        identity=text(row["node_id"],q+"/node_id",100)
        if identity not in nodes or identity in support_lookup:fail(q,"unknown_or_duplicate_support")
        dofs=distinct_texts(row["restrained_dofs"],q+"/restrained_dofs",0,6,DOFS)
        direction=row["compression_positive_direction"]
        if direction is not None:enum(direction,q+"/compression_positive_direction",("+X","-X","+Y","-Y","+Z","-Z"))
        support=dict(node_id=identity,restrained_dofs=dofs,compression_positive_direction=direction,source_reference=r.ref(row,q))
        support_lookup[identity]=support;supports.append(support)
    components=[];remaining=set(nodes)
    while remaining:
        stack=[min(remaining)];component=set()
        while stack:
            n=stack.pop()
            if n not in component:component.add(n);stack.extend(edges[n]-component)
        remaining-=component
        components.append(dict(node_ids=sorted(component),has_supplied_restrained_dof=any(v in support_lookup and support_lookup[v]["restrained_dofs"] for v in component)))
    coincident=[]
    node_ids=list(nodes)
    for i,a in enumerate(node_ids):
        for b in node_ids[i+1:]:
            distance2=sum((x-y)**2 for x,y in zip(nodes[a],nodes[b]))
            if distance2<=tolerance**2:coincident.append([a,b])
    stiffness=[];stiffness_ids=set()
    for i,row in enumerate(seq(item["stiffness_records"],p+"/stiffness_records",0,16)):
        q=p+"/stiffness_records/"+str(i)
        obj(row,q,("id","quantity","unit","value","zero_interpretation","source_reference"))
        identity=text(row["id"],q+"/id",100)
        if identity in stiffness_ids:fail(q,"duplicate_stiffness")
        stiffness_ids.add(identity)
        unit=enum(row["unit"],q+"/unit",QUANTITY_UNITS)
        value=r.n(row["value"],q+"/value",unit)
        interpretation=enum(row["zero_interpretation"],q+"/zero_interpretation",("intentional_release","physical_zero","requires_review","not_zero"))
        if (value!=0)!=(interpretation=="not_zero"):fail(q,"zero_interpretation_mismatch")
        stiffness.append(dict(id=identity,quantity=text(row["quantity"],q+"/quantity"),unit=unit,value=value,zero_interpretation=interpretation,
                              negative_value_review=value<0,zero_value_review=value==0 and interpretation!="intentional_release",source_reference=r.ref(row,q)))
    equilibrium=[];case_ids=set();tension=[]
    for i,case in enumerate(seq(item["equilibrium_cases"],p+"/equilibrium_cases",1,4)):
        q=p+"/equilibrium_cases/"+str(i)
        obj(case,q,("id","combination_id","equilibrium_basis","reference_point_m","applied_resultants","reaction_resultants","force_tolerance_kN","moment_tolerance_kNm","source_reference"))
        identity=text(case["id"],q+"/id",100)
        if identity in case_ids:fail(q,"duplicate_equilibrium_case")
        case_ids.add(identity)
        combo=text(case["combination_id"],q+"/combination_id",100)
        basis=enum(case["equilibrium_basis"],q+"/equilibrium_basis",("static","equivalent_static_inertia_included"))
        origin=vector(case["reference_point_m"],q+"/reference_point_m",r,"m")
        ft=r.n(case["force_tolerance_kN"],q+"/force_tolerance_kN","kN",ZERO)
        mt=r.n(case["moment_tolerance_kNm"],q+"/moment_tolerance_kNm","kN*m",ZERO)
        totals={};records={};inertias=0
        for group in ("applied_resultants","reaction_resultants"):
            force=[ZERO]*3;moment=[ZERO]*3;records[group]=[];ids=set()
            for j,row in enumerate(seq(case[group],q+"/"+group,1,6)):
                z=q+"/"+group+"/"+str(j)
                obj(row,z,("id","node_id","position_m","force_kN","couple_kNm","role","source_reference"))
                rid=text(row["id"],z+"/id",100)
                if rid in ids:fail(z,"duplicate_resultant")
                ids.add(rid)
                role=enum(row["role"],z+"/role",("external","inertia") if group=="applied_resultants" else ("reaction",))
                if role=="inertia":inertias+=1
                position=vector(row["position_m"],z+"/position_m",r,"m")
                f=vector(row["force_kN"],z+"/force_kN",r,"kN")
                couple=vector(row["couple_kNm"],z+"/couple_kNm",r,"kN*m")
                node=row["node_id"]
                if node is not None:
                    text(node,z+"/node_id",100)
                    if node not in nodes or any(abs(a-b)>tolerance for a,b in zip(position,nodes[node])):fail(z,"resultant_node_position_mismatch")
                arm=[a-b for a,b in zip(position,origin)];transport=cross(arm,f)
                about=[a+b for a,b in zip(couple,transport)]
                force=[a+b for a,b in zip(force,f)];moment=[a+b for a,b in zip(moment,about)]
                records[group].append(dict(id=rid,node_id=node,position_m=vecout(position),force_kN=vecout(f),couple_kNm=vecout(couple),moment_about_reference_kNm=vecout(about),role=role,source_reference=r.ref(row,z)))
                if group=="reaction_resultants" and node in support_lookup:
                    direction=support_lookup[node]["compression_positive_direction"]
                    if direction is not None:
                        component="XYZ".index(direction[1]);projection=f[component]*(1 if direction[0]=="+" else -1)
                        tension.append(dict(case_id=identity,resultant_id=rid,node_id=node,compression_positive_direction=direction,
                                            projected_compression_kN=projection,tension_candidate=projection<0))
            totals[group]=(force,moment)
        if (basis=="static" and inertias) or (basis=="equivalent_static_inertia_included" and not inertias):fail(q,"inertia_basis_mismatch")
        residual_f=[a+b for a,b in zip(totals['applied_resultants'][0],totals['reaction_resultants'][0])]
        residual_m=[a+b for a,b in zip(totals['applied_resultants'][1],totals['reaction_resultants'][1])]
        checks={"F"+axis:abs(residual_f[k])<=ft for k,axis in enumerate("XYZ")}
        checks.update({"M"+axis:abs(residual_m[k])<=mt for k,axis in enumerate("XYZ")})
        equilibrium.append(dict(id=identity,combination_id=combo,equilibrium_basis=basis,reference_point_m=vecout(origin),**records,
                                applied_force_kN=vecout(totals['applied_resultants'][0]),reaction_force_kN=vecout(totals['reaction_resultants'][0]),
                                applied_moment_kNm=vecout(totals['applied_resultants'][1]),reaction_moment_kNm=vecout(totals['reaction_resultants'][1]),
                                force_residual_kN=vecout(residual_f),moment_residual_kNm=vecout(residual_m),force_tolerance_kN=ft,moment_tolerance_kNm=mt,
                                component_within_selected_tolerance=checks,all_six_within_selected_tolerance=all(checks.values()),source_reference=r.ref(case,q)))
    topology=dict(nodes=node_rows,elements=elements,supports=supports,coordinate_tolerance_m=tolerance,
                  isolated_node_ids=sorted(set(nodes)-node_use),unknown_connectivity=unknown_nodes,zero_extent_element_ids=zero_extent,
                  connected_components=components,coincident_node_pairs=coincident,kinematic_stability_established=False,
                  ties_and_contact_equivalence_reviewed=False)
    observed=r.observed(item,p,[v for v in r.units if v.startswith(p+"/") and not v.endswith(("/coordinate_tolerance_m","/force_tolerance_kN","/moment_tolerance_kNm"))])
    if observed is not None:context["reference_date"]=observed
    study=mesh(item["mesh_study"],p+"/mesh_study",r) if "mesh_study" in item else None
    return dict(context=context,topology_review=topology,stiffness_review=stiffness,equilibrium_checks=equilibrium,
                support_compression_reviews=tension,mesh_review=study,mesh_review_status="performed_selected_comparisons" if study is not None else "not_requested")


def fe_model(data,r):
    out=common(data,r,("mode","standards"),("model","independent_beam"))
    mode=enum(data["mode"],"/mode",("model_review","beam_check"))
    if mode=="model_review" and "model" not in data or mode=="beam_check" and ("independent_beam" not in data or "model" in data):fail("data","fields_for_mode")
    standards=r.standards(data["standards"])
    model=model_review(data["model"],"/model",r) if "model" in data else None
    analytical=beam(data["independent_beam"],"/independent_beam",r) if "independent_beam" in data else None
    gaps=["selected_standard_chain_and_model_applicability_not_established"]
    if not standards:gaps.append("selected_standard_metadata_not_provided")
    if model:
        gaps += ["equilibrium_does_not_establish_stiffness_or_stability","connectivity_graph_ignores_unprovided_ties_contacts_and_releases"]
        if model["mesh_review"] is None:gaps.append("mesh_refinement_results_not_provided")
        elif any("relative_comparison_operands" in step for step in model["mesh_review"]["steps"]):gaps.append("relative_comparison_uses_unrounded_operands")
        if not model["stiffness_review"]:gaps.append("stiffness_records_not_provided")
        if any(not row["has_supplied_restrained_dof"] for row in model["topology_review"]["connected_components"]):gaps.append("component_without_supplied_restrained_dof")
        if model["topology_review"]["unknown_connectivity"]:gaps.append("unknown_element_node_references")
        if any(v["tension_candidate"] for v in model["support_compression_reviews"]):gaps.append("support_tension_candidate_requires_contact_review")
        if any(not v["all_six_within_selected_tolerance"] for v in model["equilibrium_checks"]):gaps.append("selected_equilibrium_tolerance_exceeded")
    if analytical:gaps.append("Euler_Bernoulli_beam_applicability_requires_separate_review")
    out.update(mode=mode,standards=standards,model_review=model,model_review_status="performed_selected_comparisons" if model else "not_requested",
               independent_beam=analytical,independent_beam_status="performed_selected_comparisons" if analytical else "not_requested",
               evidence_gaps=gaps,solver_executed=False,design_approval=False)
    return out


def _run(function,data):
    if function not in FUNCTIONS:fail("function","unknown")
    with localcontext(Context(prec=2400)):
        r=Read(data)
        result=loads(data,r) if function=="loads" else fe_model(data,r)
        # Unknown numeric leaves cannot be hidden in arbitrary nested metadata.
        if len(r.units)+len(r.texts)>900:fail("data","fact_limit_900")
        return exact(result),r


def execute(function,data):
    return _run(function,data)[0]


def input_units(function,data):
    return _run(function,data)[1].units


def selected_texts(function,data):
    return _run(function,data)[1].texts
