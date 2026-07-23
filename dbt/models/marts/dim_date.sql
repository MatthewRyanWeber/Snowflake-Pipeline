select
    to_number(to_char(d, 'YYYYMMDD')) as date_key,
    d                                 as full_date,
    year(d)                           as year,
    month(d)                          as month,
    day(d)                            as day,
    monthname(d)                      as month_name,
    dayofweek(d)                      as day_of_week
from (
    select dateadd(day, seq4(), '2023-01-01'::date) as d
    from table(generator(rowcount => 1461))
)
where d <= '2026-12-31'::date
