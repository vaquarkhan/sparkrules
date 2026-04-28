{{ config(alias='clinical_labs_staged') }}

/*
  Author: Vaquar Khan
  Mirrors examples/usecases/clinical_research/staging.py enrichment in SQL so analysts can QA
  canonical hints before handing rows to SparkRules/DRL downstream.
*/

with seed as (
  select * from {{ ref('clinical_labs_sample') }}
),

typed as (
  select
    *,
    trim(raw_value) as raw_value_trimmed,
    try_cast(trim(raw_value) as double) as numeric_value
  from seed
),

enriched as (
  select
    *,
    case
      when measure_code = 'WT' and lower(trim(raw_unit)) = 'lb' and numeric_value is not null
      then round(numeric_value / 2.2046226218, 3)
    end as wt_pref_kg,
    case
      when measure_code = 'WT' and lower(trim(raw_unit)) = 'lb' and numeric_value is not null
      then numeric_value / round(numeric_value / 2.2046226218, 3)
    end as conv_factor_lb_to_kg,
    case
      when measure_code = 'GLUCOSE' and lower(trim(raw_unit)) = 'mmol/l' and numeric_value is not null
      then round(numeric_value * 18.0182, 1)
    end as glucose_pref_mgdL,
    case
      when measure_code = 'GLUCOSE' and lower(trim(raw_unit)) = 'mmol/l' and numeric_value is not null
      then (round(numeric_value * 18.0182, 1)) / numeric_value
    end as conv_factor_mmol_to_mgdL,
    case
      when measure_code = 'HGB' and lower(trim(coalesce(raw_unit, ''))) = 'g/l'
      and numeric_value is not null
      then round(numeric_value / 10.0, 2)
    end as hgb_pref_gdl,
    case
      when measure_code = 'HGB' and lower(trim(coalesce(raw_unit, ''))) = 'g/l'
      and numeric_value is not null
      then numeric_value / round(numeric_value / 10.0, 2)
    end as conv_factor_gl_per_gdl,
    case
      when measure_code = 'ALT' and upper(trim(coalesce(raw_unit, ''))) = 'U/L'
      and numeric_value is not null
      then round(numeric_value / 1000.0, 3)
    end as alt_pref_kul,
    case
      when measure_code = 'ALT' and upper(trim(coalesce(raw_unit, ''))) = 'U/L'
      and numeric_value is not null
      then numeric_value / round(numeric_value / 1000.0, 3)
    end as conv_factor_ul_to_kul
  from typed
)

select * from enriched
