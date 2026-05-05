//! Tier-1 scalar scoring: mirrors ``compile_predicate`` / ``AlphaNetwork`` / ``LocalRuleExecutor.score``.

use std::collections::BTreeMap;

use regex::Regex;
use serde_json::{json, Map, Number, Value as JsonValue};

use crate::actions::action_field_name;
use crate::ast::{BinaryOperator, Expr, FactPatternJson, RuleJson, RulePackJson};
use crate::errors::NativeError;

#[derive(Clone)]
pub struct NativeRule {
    pub name: String,
    pub salience: i32,
    pub source_order: usize,
    pub reason_codes: Vec<String>,
    pub wildcard: bool,
    pub atomics: Vec<Expr>,
    pub actions: Vec<(String, Expr)>,
}

#[derive(Clone)]
pub struct NativePack {
    pub drl_hash: String,
    pub rules: Vec<NativeRule>,
}

impl NativePack {
    pub fn from_pack_json(parsed: RulePackJson) -> Result<Self, NativeError> {
        if parsed.native_schema != crate::ast::NATIVE_SCHEMA {
            return Err(NativeError::Compile(format!(
                "unsupported native_schema '{}' (expected '{}')",
                parsed.native_schema,
                crate::ast::NATIVE_SCHEMA
            )));
        }
        let rules: Result<Vec<_>, NativeError> = parsed
            .rules
            .into_iter()
            .map(NativeRule::from_rule_json)
            .collect();
        Ok(NativePack {
            drl_hash: parsed.drl_hash,
            rules: rules?,
        })
    }
}

impl NativeRule {
    fn from_rule_json(r: RuleJson) -> Result<Self, NativeError> {
        let wildcard = is_wildcard(&r.when);
        let atomics = if wildcard {
            Vec::new()
        } else {
            flatten_and(r.when[0].constraint.as_ref().ok_or_else(|| {
                NativeError::Compile(format!("rule {} missing constraint", r.name))
            })?)
        };
        let actions: Vec<(String, Expr)> = r
            .then
            .iter()
            .map(|a| (action_field_name(&a.field_path), a.expr.clone()))
            .collect();
        Ok(NativeRule {
            name: r.name,
            salience: r.salience,
            source_order: r.source_order,
            reason_codes: r.reason_codes,
            wildcard,
            atomics,
            actions,
        })
    }
}

fn is_wildcard(when: &[FactPatternJson]) -> bool {
    when.len() != 1 || when[0].constraint.is_none()
}

pub fn flatten_and(expr: &Expr) -> Vec<Expr> {
    match expr {
        Expr::BinaryOp {
            op: BinaryOperator::And,
            left,
            right,
        } => {
            let mut out = flatten_and(left);
            out.extend(flatten_and(right));
            out
        }
        _ => vec![expr.clone()],
    }
}

#[inline]
fn safe_bool<F>(f: F) -> bool
where
    F: FnOnce() -> bool,
{
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)).unwrap_or(false)
}

fn stringify_for_matches(v: &JsonValue) -> String {
    match v {
        JsonValue::Null => "None".into(),
        JsonValue::Bool(b) => b.to_string(),
        JsonValue::Number(n) => n.to_string(),
        JsonValue::String(s) => s.clone(),
        x => x.to_string(),
    }
}

/// Drools-like ``contains`` (``closure.contains_semantics``).
pub fn contains_semantics(container: &JsonValue, needle: &JsonValue) -> bool {
    match container {
        JsonValue::Array(a) => a.iter().any(|x| x == needle),
        JsonValue::Object(m) => match needle {
            JsonValue::String(s) => m.contains_key(s.as_str()),
            JsonValue::Number(n) => m.contains_key(&n.to_string()),
            JsonValue::Bool(b) => m.contains_key(&b.to_string()),
            JsonValue::Null => m.contains_key("null"),
            _ => false,
        },
        other => {
            let left_s = match other {
                JsonValue::Null => String::new(),
                JsonValue::String(s) => s.clone(),
                _ => stringify_for_matches(other),
            };
            let right_s = match needle {
                JsonValue::Null => String::new(),
                JsonValue::String(s) => s.clone(),
                _ => stringify_for_matches(needle),
            };
            !(left_s.is_empty() && right_s.is_empty()) && left_s.contains(right_s.as_str())
        }
    }
}

fn as_collection<'a>(v: &'a JsonValue) -> Vec<&'a JsonValue> {
    match v {
        JsonValue::Array(a) => a.iter().collect(),
        JsonValue::Null => vec![&JsonValue::Null],
        other => vec![other],
    }
}

fn in_membership(member: &JsonValue, hay: &JsonValue, negated: bool) -> bool {
    let coll = as_collection(hay);
    let hit = coll.iter().any(|x| *x == member);
    if negated {
        !hit
    } else {
        hit
    }
}

fn resolve_identifier(name: &str, fact: &JsonValue) -> JsonValue {
    let mut nm = name;
    if let Some(rest) = nm.strip_prefix('$') {
        nm = rest;
    }
    let parts: Vec<&str> = nm.split('.').collect();
    let mut cur = fact;
    for p in parts {
        match cur.get(p) {
            Some(next) => cur = next,
            None => return JsonValue::Null,
        }
    }
    cur.clone()
}

fn resolve_field_access(base: &str, field: &str, fact: &JsonValue) -> JsonValue {
    fact.get(base)
        .and_then(|o| {
            if let JsonValue::Object(m) = o {
                m.get(field).cloned()
            } else {
                None
            }
        })
        .unwrap_or(JsonValue::Null)
}

fn truthy_json(v: &JsonValue) -> bool {
    match v {
        JsonValue::Null => false,
        JsonValue::Bool(b) => *b,
        JsonValue::Number(n) => n
            .as_i64()
            .map(|i| i != 0)
            .unwrap_or_else(|| n.as_f64().map(|f| f != 0.0).unwrap_or(false)),
        JsonValue::String(s) => !s.is_empty(),
        JsonValue::Array(a) => !a.is_empty(),
        JsonValue::Object(m) => !m.is_empty(),
    }
}

fn compare_values(left: &JsonValue, right: &JsonValue, op: BinaryOperator) -> bool {
    match op {
        BinaryOperator::Eq => left == right,
        BinaryOperator::Ne => left != right,
        BinaryOperator::Lt => json_cmp(left, right).map(|o| o.is_lt()).unwrap_or(false),
        BinaryOperator::Le => json_cmp(left, right)
            .map(|o| matches!(o, std::cmp::Ordering::Less | std::cmp::Ordering::Equal))
            .unwrap_or(false),
        BinaryOperator::Gt => json_cmp(left, right).map(|o| o.is_gt()).unwrap_or(false),
        BinaryOperator::Ge => json_cmp(left, right)
            .map(|o| matches!(o, std::cmp::Ordering::Greater | std::cmp::Ordering::Equal))
            .unwrap_or(false),
        BinaryOperator::Contains => contains_semantics(left, right),
        BinaryOperator::Matches => {
            let pat = stringify_for_matches(right);
            Regex::new(&pat).ok().map_or(false, |re| {
                let hay = stringify_for_matches(left);
                re.find(&hay).is_some()
            })
        }
        BinaryOperator::In | BinaryOperator::NotIn => {
            in_membership(left, right, op == BinaryOperator::NotIn)
        }
        _ => false,
    }
}

fn json_cmp(a: &JsonValue, b: &JsonValue) -> Option<std::cmp::Ordering> {
    match (a, b) {
        (JsonValue::Null, _) | (_, JsonValue::Null) => None,
        (JsonValue::Bool(x), JsonValue::Bool(y)) => Some(x.cmp(y)),
        (JsonValue::String(x), JsonValue::String(y)) => Some(x.cmp(y)),
        (JsonValue::Number(x), JsonValue::Number(y)) => {
            let xf = x.as_f64().or_else(|| x.as_u64().map(|u| u as f64))?;
            let yf = y.as_f64().or_else(|| y.as_u64().map(|u| u as f64))?;
            xf.partial_cmp(&yf)
        }
        _ => None,
    }
}

/// Predicate evaluation matching ``compile_predicate`` (panic-safe layer like `_safe`).
pub fn eval_predicate(expr: &Expr, fact: &JsonValue) -> bool {
    match expr {
        Expr::Literal { value } => truthy_json(value),
        Expr::Identifier { name } => truthy_json(&resolve_identifier(name, fact)),
        Expr::Not { expr: inner } => !safe_bool(|| eval_predicate(inner, fact)),
        Expr::BinaryOp {
            op: BinaryOperator::And,
            left,
            right,
        } => safe_bool(|| eval_predicate(left, fact)) && safe_bool(|| eval_predicate(right, fact)),
        Expr::BinaryOp {
            op: BinaryOperator::Or,
            left,
            right,
        } => safe_bool(|| eval_predicate(left, fact)) || safe_bool(|| eval_predicate(right, fact)),
        Expr::BinaryOp { op, left, right } => safe_bool(|| {
            let lv = resolve_operand_value(left, fact);
            let rv = resolve_operand_value(right, fact);
            compare_values(&lv, &rv, *op)
        }),
        Expr::InExpr {
            left,
            right,
            negated,
        } => safe_bool(|| {
            let lv = resolve_operand_value(left, fact);
            let rv = resolve_operand_value(right, fact);
            in_membership(&lv, &rv, *negated)
        }),
        _ => safe_bool(|| truthy_json(&eval_value(expr, fact).unwrap_or(JsonValue::Null))),
    }
}

fn resolve_operand_value(expr: &Expr, fact: &JsonValue) -> JsonValue {
    eval_value(expr, fact).unwrap_or(JsonValue::Null)
}

pub fn eval_value(expr: &Expr, fact: &JsonValue) -> Result<JsonValue, ()> {
    match expr {
        Expr::Literal { value } => Ok(value.clone()),
        Expr::Identifier { name } => Ok(resolve_identifier(name, fact)),
        Expr::FieldAccess { base, field } => Ok(resolve_field_access(base, field, fact)),
        Expr::ListExpr { items } => {
            let mut v = Vec::with_capacity(items.len());
            for it in items {
                v.push(eval_value(it, fact)?);
            }
            Ok(JsonValue::Array(v))
        }
        Expr::BinaryOp {
            op: BinaryOperator::And,
            left,
            right,
        } => Ok(JsonValue::Bool(
            eval_predicate(left, fact) && eval_predicate(right, fact),
        )),
        Expr::BinaryOp {
            op: BinaryOperator::Or,
            left,
            right,
        } => Ok(JsonValue::Bool(
            eval_predicate(left, fact) || eval_predicate(right, fact),
        )),
        Expr::BinaryOp { op, left, right } => {
            let lv = resolve_operand_value(left, fact);
            let rv = resolve_operand_value(right, fact);
            Ok(JsonValue::Bool(compare_values(&lv, &rv, *op)))
        }
        Expr::Not { expr } => Ok(JsonValue::Bool(!eval_predicate(expr, fact))),
        Expr::InExpr {
            left,
            right,
            negated,
        } => {
            let lv = eval_value(left, fact)?;
            let rv = eval_value(right, fact)?;
            Ok(JsonValue::Bool(in_membership(&lv, &rv, *negated)))
        }
        Expr::CallExpr { name, args } => {
            let mut arg_vals = Vec::new();
            for a in args {
                arg_vals.push(eval_value(a, fact)?);
            }
            eval_builtin_call(name, &arg_vals)
        }
    }
}

fn eval_builtin_call(name: &str, args: &[JsonValue]) -> Result<JsonValue, ()> {
    match name {
        "len" => {
            let a = args.first().ok_or(())?;
            match a {
                JsonValue::String(s) => {
                    Ok(JsonValue::Number(Number::from(s.chars().count() as i64)))
                }
                JsonValue::Array(v) => Ok(JsonValue::Number(Number::from(v.len() as i64))),
                JsonValue::Object(m) => Ok(JsonValue::Number(Number::from(m.len() as i64))),
                _ => Err(()),
            }
        }
        "str" => Ok(JsonValue::String(stringify_for_matches(
            args.first().ok_or(())?,
        ))),
        "int" => match args.first().ok_or(())? {
            JsonValue::Number(n) => {
                if let Some(i) = n.as_i64() {
                    Ok(JsonValue::Number(Number::from(i)))
                } else if let Some(f) = n.as_f64() {
                    Ok(JsonValue::Number(
                        serde_json::Number::from_f64(f).ok_or(())?,
                    ))
                } else {
                    Err(())
                }
            }
            JsonValue::String(s) => Ok(JsonValue::Number(Number::from(
                s.trim().parse::<i64>().map_err(|_| ())?,
            ))),
            _ => Err(()),
        },
        "float" => {
            let f = match args.first().ok_or(())? {
                JsonValue::Number(n) => n.as_f64().ok_or(())?,
                JsonValue::String(s) => s.trim().parse::<f64>().map_err(|_| ())?,
                _ => return Err(()),
            };
            Ok(JsonValue::Number(
                serde_json::Number::from_f64(f).ok_or(())?,
            ))
        }
        "abs" => {
            let a = args.first().ok_or(())?;
            match a {
                JsonValue::Number(n) => {
                    if let Some(i) = n.as_i64() {
                        Ok(JsonValue::Number(Number::from(i.abs())))
                    } else if let Some(f) = n.as_f64() {
                        let v = serde_json::Number::from_f64(f.abs()).ok_or(())?;
                        Ok(JsonValue::Number(v))
                    } else {
                        Err(())
                    }
                }
                _ => Err(()),
            }
        }
        _ => Ok(JsonValue::Null),
    }
}

pub fn score_row_json(pack: &NativePack, fact_json: &str) -> Result<String, NativeError> {
    let fact: JsonValue = serde_json::from_str(fact_json)?;
    let out = score_row_value(pack, &fact);
    serde_json::to_string(&out).map_err(|e| NativeError::Score(e.to_string()))
}

fn merge_actions_skeleton() -> BTreeMap<String, JsonValue> {
    BTreeMap::new()
}

pub(crate) fn score_row_value(pack: &NativePack, fact: &JsonValue) -> JsonValue {
    let mut merged = merge_actions_skeleton();
    let mut any_fired = false;
    let mut fires_arr = Vec::new();

    for rule in &pack.rules {
        let fired = if rule.wildcard {
            true
        } else {
            rule.atomics.iter().all(|atom| eval_predicate(atom, fact))
        };

        let mut action_output: Map<String, JsonValue> = Map::new();

        if fired {
            any_fired = true;
            for (field, expr) in &rule.actions {
                let val = eval_value(expr, fact).unwrap_or(JsonValue::Null);
                action_output.insert(field.clone(), val.clone());
                merged.entry(field.clone()).or_insert(val);
            }
        }

        fires_arr.push(json!({
            "rule_name": rule.name,
            "salience": rule.salience,
            "fired": fired,
            "action_output": action_output,
            "reason_codes": rule.reason_codes,
        }));
    }

    json!({
        "fires": fires_arr,
        "fired_any": any_fired,
        "merged_actions": merged.into_iter().collect::<serde_json::Map<_, _>>(),
    })
}
