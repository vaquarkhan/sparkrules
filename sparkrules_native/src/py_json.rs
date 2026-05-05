//! Python ``dict`` / list / scalars ↔ ``serde_json::Value`` for Tier‑1 FFI
//! (avoids ``json.dumps`` / ``json.loads`` across the PyO3 boundary).

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyList, PyNone, PyString, PyTuple};
use pyo3::IntoPyObject;

use serde_json::{Number, Value as JsonValue};

pub fn py_to_json_value(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<JsonValue> {
    if obj.is_none() {
        return Ok(JsonValue::Null);
    }
    if obj.is_instance_of::<PyBool>() {
        return Ok(JsonValue::Bool(obj.extract::<bool>()?));
    }
    if let Ok(i) = obj.extract::<i64>() {
        return Ok(JsonValue::Number(i.into()));
    }
    if let Ok(u) = obj.extract::<u64>() {
        return Ok(JsonValue::Number(u.into()));
    }
    if let Ok(f) = obj.extract::<f64>() {
        return Number::from_f64(f)
            .map(JsonValue::Number)
            .ok_or_else(|| PyValueError::new_err("native FFI: non-finite float"));
    }
    if let Ok(s) = obj.extract::<String>() {
        return Ok(JsonValue::String(s));
    }

    if let Ok(d) = obj.downcast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in d.iter() {
            let key = k.extract::<String>()?;
            map.insert(key, py_to_json_value(py, &v)?);
        }
        return Ok(JsonValue::Object(map));
    }

    if let Ok(list) = obj.downcast::<PyList>() {
        let mut out = Vec::with_capacity(list.len());
        for i in 0..list.len() {
            let it = list.get_item(i)?;
            out.push(py_to_json_value(py, &it)?);
        }
        return Ok(JsonValue::Array(out));
    }

    if let Ok(tup) = obj.downcast::<PyTuple>() {
        let mut out = Vec::with_capacity(tup.len());
        for i in 0..tup.len() {
            let it = tup.get_item(i)?;
            out.push(py_to_json_value(py, &it)?);
        }
        return Ok(JsonValue::Array(out));
    }

    // ``json.dumps(..., default=str)``
    let s = obj.str()?.extract::<String>()?;
    Ok(JsonValue::String(s))
}

pub fn json_value_to_py<'py>(
    py: Python<'py>,
    v: &JsonValue,
) -> PyResult<Bound<'py, PyAny>> {
    match v {
        JsonValue::Null => Ok(PyNone::get_bound(py).into_any()),
        JsonValue::Bool(b) => Ok(PyBool::new_bound(py, *b).into_any()),
        JsonValue::Number(n) => number_to_py(py, n),
        JsonValue::String(s) => Ok(PyString::new_bound(py, s.as_str()).into_any()),
        JsonValue::Array(items) => {
            let list = PyList::empty_bound(py);
            for it in items {
                list.append(json_value_to_py(py, it)?)?;
            }
            Ok(list.into_any())
        }
        JsonValue::Object(m) => {
            let d = PyDict::new_bound(py);
            for (k, vv) in m.iter() {
                d.set_item(k.as_str(), json_value_to_py(py, vv)?)?;
            }
            Ok(d.into_any())
        }
    }
}

fn number_to_py<'py>(py: Python<'py>, n: &Number) -> PyResult<Bound<'py, PyAny>> {
    if let Some(i) = n.as_i64() {
        let b = i.into_pyobject(py)?;
        return Ok(b.into_any());
    }
    if let Some(u) = n.as_u64() {
        let b = u.into_pyobject(py)?;
        return Ok(b.into_any());
    }
    if let Some(f) = n.as_f64() {
        return Ok(PyFloat::new_bound(py, f).into_any());
    }
    Err(PyValueError::new_err("native FFI: invalid JSON number"))
}
