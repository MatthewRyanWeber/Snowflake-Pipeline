{% snapshot patient_snapshot %}
{{ config(
     target_schema='DBT_SNAPSHOTS',
     unique_key='patient_id',
     strategy='check',
     check_cols=['first_name','last_name','birth_date','gender','city','state']
) }}
select * from {{ ref('stg_patients') }}
{% endsnapshot %}
