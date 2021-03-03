def future_monthly_salary(s, work_years, total_years, stocks_count, stock_value, exercise_price):
    work_months = work_years * 12
    passive_months = (total_years - work_years) * 12
    h = 0
    hb = 0
    for m in range(work_months):
        h *= 1.004
        h += s
        hb += s
    for m in range(passive_months):
        h *= 1.004
    total_salary = hb + (h - hb) * 0.75
    total_stocks = stocks_count * (stock_value - exercise_price) * 0.75
    return (total_salary + total_stocks) / work_months
