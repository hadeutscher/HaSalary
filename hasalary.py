#!/usr/bin/env python3
# coding: utf-8

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import math
import itertools
import argparse

### Universal constants ###
AVERAGE_SALARY = 10551
STUDY_FUND_EMPLOYEE = 0.025
STUDY_FUND_EMPLOYER = 0.075

### Income Tax law ###
INCOME_TAX_POINT_WORTH = 2628 / 12 # Section 33a

# Section 121
INCOME_TAX_STEPS = [
    (75960 / 12, 0.10),
    (108960 / 12, 0.14),
    (174960 / 12, 0.20),
    (243120 / 12, 0.31),
    (504360 / 12, 0.35),
    (651600 / 12, 0.47),
    (math.inf, 0.50)
    ]

PENSION_REIMBURSE = 0.35 # Section 45a(b)
PENSION_REIMBURSE_PAYMENTS_MAX = 105600 * 0.07 / 12 # Section 47(a)(1), also see 45a(d)(2)(b)(2), 45a(e)(2)(b)(2)(a)
PENSION_EMPLOYER_TAX_EXEMPT_SALARY_MAX = AVERAGE_SALARY * 2.5 # Section 3(e3)(2)
PENSION_REPARATIONS_TAX_EXEMPT_SALARY_MAX = 34900 / 12 # Section 3(e3)(2)
STUDY_FUND_TAX_EXEMPT_MAX = 15712 # Section 3(e)
REPARATIONS_PULL_TAX_EXEMPT_MAX = 12420 / 12 # Section 7a(a)(2)

### National Insurance law ###
# Right hand is National Insurance and Health Insurance, respectively
NATIONAL_INSURANCE_STEPS = [
    (AVERAGE_SALARY * 0.6, 0.004 + 0.031),
    (44020, 0.07 + 0.05)
    ]

def tax_steps(s, steps):
    tax = 0
    last_step = 0
    for step, tax_rate in steps:
        tax += tax_rate * (min(step, s) - last_step)
        last_step = step
        if s <= step:
            break
    return tax


def income_tax(s, pts):
    return max(tax_steps(s, INCOME_TAX_STEPS) - (INCOME_TAX_POINT_WORTH * pts), 0)


def national_insurance(s):
    return tax_steps(s, NATIONAL_INSURANCE_STEPS)

postprocess = lambda x: x

def main():
    # Loading config
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=str, help="config to be used")
    args = parser.parse_args()
    with open(f"{args.config}", "r", encoding="utf-8") as f:
        d = {}
        exec(f.read(), d)
        globals().update(d)

    salary = base_salary * percentage + travel_allowance + bonuses
    tax_worth_features = ten_bis + goods

    # Social payments
    social_salary = base_salary * percentage
    pens = PENSION_EMPLOYEE * social_salary
    if social_salary > PENSION_EMPLOYER_TAX_EXEMPT_SALARY_MAX:
        # Zkifat Tagmulim
        tax_worth_features += (social_salary - PENSION_EMPLOYER_TAX_EXEMPT_SALARY_MAX) * PENSION_EMPLOYER
    reparations = PENSION_REPERATIONS * social_salary
    if reparations > PENSION_REPARATIONS_TAX_EXEMPT_SALARY_MAX:
        # Zkifat Pitzuiim
        tax_worth_features += reparations - PENSION_REPARATIONS_TAX_EXEMPT_SALARY_MAX
    if social_salary > STUDY_FUND_TAX_EXEMPT_MAX and full_study_fund:
        # Zkifat Hishtalmut
        tax_worth_features += (social_salary - STUDY_FUND_TAX_EXEMPT_MAX) * STUDY_FUND_EMPLOYER
        sfund = STUDY_FUND_EMPLOYEE * social_salary
    else:
        sfund = STUDY_FUND_EMPLOYEE * STUDY_FUND_TAX_EXEMPT_MAX

    # National Insurance
    salary_for_natins = salary + tax_worth_features
    natins_tax = national_insurance(salary_for_natins)

    # Income Tax
    salary_for_income = salary + tax_worth_features - tax_worth_expenses
    salary_for_income -= PENSION_REIMBURSE * min(pens, PENSION_REIMBURSE_PAYMENTS_MAX)
    salary_for_income -= STUDY_FUND_EMPLOYEE * min(social_salary, STUDY_FUND_TAX_EXEMPT_MAX)
    in_tax = income_tax(salary_for_income, tax_pts)

    # Part 1 (paycheck)
    netto_salary = salary - in_tax - natins_tax - pens - sfund
    print("---Paycheck details---")
    print(f"Income tax: {round(in_tax)} from a salary of {round(salary_for_income)} with {tax_pts} points")
    print(f"National Insurance: {round(natins_tax)} from a salary of {round(salary_for_natins)}")
    print(f"Pension: {round(pens)} from a salary of {round(social_salary)}")
    print(f"Study Fund: {round(sfund)} from a salary of {round(social_salary)}")
    print(f"Salary (Net): {round(netto_salary)}")
    print("-------------------------------------")

    # Part 2 (total income)
    reparations_cash = min(reparations, REPARATIONS_PULL_TAX_EXEMPT_MAX)
    if reparations > PENSION_REPARATIONS_TAX_EXEMPT_SALARY_MAX:
        reparations_cash += reparations - PENSION_REPARATIONS_TAX_EXEMPT_SALARY_MAX
    sfund_cash = (STUDY_FUND_EMPLOYEE + STUDY_FUND_EMPLOYER) * (social_salary if full_study_fund else min(social_salary, STUDY_FUND_TAX_EXEMPT_MAX))
    total_monthly_income = netto_salary + reparations_cash + sfund_cash
    total_monthly_income = postprocess(total_monthly_income)
    print("---Other stats---")
    print(f"Reparations cash: {round(reparations_cash)}")
    print(f"Study fund cash: {round(sfund_cash)}")

    # Part 3 (savings)
    if target is None:
        return
    monthly_gain = total_monthly_income - monthly_expense
    target_amount = monthly_expense * SELF_SUSTAINMENT if target is None else target
    monthly_gain_rate = 1 + (yearly_gain_rate - 1) / 12
    for i in itertools.count():
        if current_cash * monthly_gain_rate ** i + sum(monthly_gain * monthly_gain_rate ** j for j in range(i)) >= target_amount:
            years = i / 12
            break
    print(f"{years:.1f} years to reach target of {round(target_amount)} with {round(monthly_gain)} monthly saving")


if __name__ == "__main__":
    main()
