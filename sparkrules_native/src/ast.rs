//! Parsed rulepack JSON (mirrors `sparkrules.parser.ast`, serializer: `sparkrules.native.ast_json`).

use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

pub const NATIVE_SCHEMA: &str = "1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[allow(clippy::enum_variant_names)]
pub enum BinaryOperator {
    #[serde(rename = "==")]
    Eq,
    #[serde(rename = "!=")]
    Ne,
    #[serde(rename = "<")]
    Lt,
    #[serde(rename = "<=")]
    Le,
    #[serde(rename = ">")]
    Gt,
    #[serde(rename = ">=")]
    Ge,
    #[serde(rename = "and")]
    And,
    #[serde(rename = "or")]
    Or,
    #[serde(rename = "in")]
    In,
    #[serde(rename = "not in")]
    NotIn,
    #[serde(rename = "contains")]
    Contains,
    #[serde(rename = "matches")]
    Matches,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "PascalCase")]
pub enum Expr {
    Literal {
        value: JsonValue,
    },
    Identifier {
        name: String,
    },
    ListExpr {
        items: Vec<Expr>,
    },
    InExpr {
        left: Box<Expr>,
        right: Box<Expr>,
        negated: bool,
    },
    CallExpr {
        name: String,
        args: Vec<Expr>,
    },
    FieldAccess {
        base: String,
        field: String,
    },
    BinaryOp {
        op: BinaryOperator,
        left: Box<Expr>,
        right: Box<Expr>,
    },
    Not {
        expr: Box<Expr>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FactPatternJson {
    pub bind_name: String,
    pub fact_type: String,
    pub constraint: Option<Expr>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionJson {
    pub field_path: String,
    pub expr: Expr,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleJson {
    pub name: String,
    pub salience: i32,
    pub source_order: usize,
    pub reason_codes: Vec<String>,
    pub when: Vec<FactPatternJson>,
    pub then: Vec<ActionJson>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RulePackJson {
    pub drl_hash: String,
    pub native_schema: String,
    pub rules: Vec<RuleJson>,
}

#[cfg(test)]
mod serde_smoke {
    use super::*;

    #[test]
    fn binary_op_deser() {
        let j = serde_json::json!({
            "kind": "BinaryOp",
            "op": "==",
            "left": {"kind": "Literal", "value": 1},
            "right": {"kind": "Literal", "value": 1}
        });
        let _: Expr = serde_json::from_value(j).expect("expr");
    }

    #[test]
    fn lowercase_and_op() {
        let j = serde_json::json!({
            "kind": "BinaryOp",
            "op": "and",
            "left": {"kind": "Literal", "value": true},
            "right": {"kind": "Literal", "value": false}
        });
        let _: Expr = serde_json::from_value(j).expect("and");
    }

    #[test]
    fn operators_in_contains_matches() {
        for (op, tpl) in [
            (
                "not in",
                serde_json::json!({
                    "kind": "InExpr",
                    "left": {"kind": "Literal", "value": 1},
                    "right": {"kind": "ListExpr", "items": []},
                    "negated": true
                }),
            ),
            (
                "contains",
                serde_json::json!({
                    "kind": "BinaryOp",
                    "op": "contains",
                    "left": {"kind": "Literal", "value": "hay"},
                    "right": {"kind": "Literal", "value": "a"}
                }),
            ),
            (
                "matches",
                serde_json::json!({
                    "kind": "BinaryOp",
                    "op": "matches",
                    "left": {"kind": "Literal", "value": "x"},
                    "right": {"kind": "Literal", "value": "."}
                }),
            ),
        ] {
            let _: Expr = serde_json::from_value(tpl).unwrap_or_else(|e| panic!("parse {op}: {e}"));
        }
    }
}
