import sys

import duckdb

path = sys.argv[1]
con = duckdb.connect()
con.read_parquet(path).create_view("s")

print("Rows in Commerce, GA or with evacuation_capacity > 20,000")
con.sql(
    """
    select shelter_name, city, county_name, usage,
           evacuation_capacity, post_impact_capacity, shelter_status_code
    from s
    where upper(city) = 'COMMERCE' or evacuation_capacity > 20000
    order by evacuation_capacity desc nulls last
    """
).show(max_width=200)

print("Post-impact capacity = half of evacuation capacity (20 vs 40 sq ft per person), by usage")
con.sql(
    """
    select usage,
           count(*) as shelters,
           count(*) filter (where evacuation_capacity > 0
                            and abs(post_impact_capacity - evacuation_capacity / 2) <= 1) as post_is_half,
           count(*) filter (where evacuation_capacity > 0 and post_impact_capacity = 0) as post_zero
    from s
    group by usage
    order by usage nulls last
    """
).show()

print("Share of reported evacuation capacity held by the two Commerce school rows")
con.sql(
    """
    select sum(evacuation_capacity) as total,
           sum(evacuation_capacity) filter (where shelter_name in
               ('Commerce High School', 'Commerce Primary School') and upper(city) = 'COMMERCE') as commerce_two,
           round(100 * commerce_two / total, 1) as pct
    from s
    """
).show()
