#!/usr/bin/env python3
# coding: utf-8

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import itertools
import argparse
import os.path


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


def postprocess(x): return x


def main():
    # Loading config
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=str, help="config to be used")
    args = parser.parse_args()
    with open(f"{args.config}", "r", encoding="utf-8") as f:
        d = {}
        exec(f.read(), d)
        globals().update(d)

    try:
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "constants", f"{TAX_YEAR}.py"), "r", encoding="utf-8") as f:
            d = {}
            exec(f.read(), d)
            globals().update(d)
    except FileNotFoundError:
        print(f"Tax calculations for {TAX_YEAR} not supported")
        return

    if independent_mode:
        salary = base_salary * percentage
        social_salary = salary - tax_worth_expenses
        salary_for_natins = salary - tax_worth_expenses

        # Social paymens
        salary_for_pens = min(social_salary - tax_worth_expenses, PENSION_INDEPENDENT_MAX_SALARY)
        pens_a = PENSION_INDEPENDENT_RATE_WRITEOFF * salary_for_pens
        pens_b = (PENSION_INDEPENDENT_RATE_REIMBURSE + PENSION_INDEPENDENT_RATE_REIMBURSE_ACA) * salary_for_pens
        pens = pens_a + pens_b
        sfund = STUDY_FUND_INDEPENDENT * \
            min(social_salary, STUDY_FUND_INDEPENDENT_MAX_SALARY)

        # National insurance
        natins_tax = tax_steps(
            salary_for_natins, INDEPENDENT_NATIONAL_INSURANCE_STEPS)
        healthins_tax = tax_steps(salary_for_natins, HEALTH_INSURANCE_STEPS)

        # Income tax
        salary_for_income = salary - tax_worth_expenses - pens_a - sfund
        in_tax = income_tax(salary_for_income, tax_pts)
        in_tax -= PENSION_REIMBURSE * pens_b
    else:
        salary = base_salary * percentage + travel_allowance + bonuses
        tax_worth_features = ten_bis + goods

        # Social payments
        social_salary = base_salary * percentage
        pens = PENSION_EMPLOYEE * social_salary
        pens_employer = PENSION_EMPLOYER * social_salary
        if pens_employer > PENSION_EMPLOYER_TAX_EXEMPT_PAYMENTS_MAX:
            # Zkifat Tagmulim
            tax_worth_features += pens_employer - PENSION_EMPLOYER_TAX_EXEMPT_PAYMENTS_MAX
        reparations = PENSION_REPARATIONS * social_salary
        if reparations > PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX:
            # Zkifat Pitzuiim
            tax_worth_features += reparations - PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX
        if social_salary > STUDY_FUND_TAX_EXEMPT_MAX and full_study_fund:
            # Zkifat Hishtalmut
            tax_worth_features += (social_salary -
                                   STUDY_FUND_TAX_EXEMPT_MAX) * STUDY_FUND_EMPLOYER
            sfund = STUDY_FUND_EMPLOYEE * social_salary
        else:
            sfund = STUDY_FUND_EMPLOYEE * \
                min(social_salary, STUDY_FUND_TAX_EXEMPT_MAX)

        # National Insurance
        salary_for_natins = salary + tax_worth_features
        natins_tax = tax_steps(salary_for_natins, NATIONAL_INSURANCE_STEPS)
        healthins_tax = tax_steps(salary_for_natins, HEALTH_INSURANCE_STEPS)

        # Income Tax
        salary_for_income = salary + tax_worth_features - tax_worth_expenses
        in_tax = income_tax(salary_for_income, tax_pts)
        in_tax -= PENSION_REIMBURSE * min(pens, PENSION_REIMBURSE_PAYMENTS_MAX)

    # Part 1 (paycheck)
    netto_salary = salary - in_tax - natins_tax - healthins_tax - pens - sfund
    print("---Paycheck details---")
    print(
        f"Income tax: {round(in_tax)} from a salary of {round(salary_for_income)} with {tax_pts} points")
    print(
        f"National Insurance: {round(natins_tax)} from a salary of {round(salary_for_natins)}")
    print(
        f"Health Insurance: {round(healthins_tax)} from a salary of {round(salary_for_natins)}")
    print(f"Pension: {round(pens)} from a salary of {round(social_salary)}")
    print(
        f"Study Fund: {round(sfund)} from a salary of {round(social_salary)}")
    print(f"Salary (Net): {round(netto_salary)}")
    print("-------------------------------------")

    # Part 2 (total income)
    if independent_mode:
        reparations_cash = 0
        employer_sfund = 0
    else:
        reparations_cash = min(reparations, REPARATIONS_PULL_TAX_EXEMPT_MAX)
        if reparations > PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX:
            reparations_cash += reparations - PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX
        if include_pension:
            reparations_cash = reparations
        elif monthly_reparations_pull and reparations > REPARATIONS_PULL_TAX_EXEMPT_MAX:
            taxed_reparations = reparations - reparations_cash
            tax_rate = income_tax(monthly_reparations_pull,
                                  tax_pts) / monthly_reparations_pull
            reparations_cash += taxed_reparations * (1 - tax_rate)
        employer_sfund = STUDY_FUND_EMPLOYER * \
            (social_salary if full_study_fund else min(
                social_salary, STUDY_FUND_TAX_EXEMPT_MAX))

    sfund_cash = sfund + employer_sfund
    pens_total = pens if independent_mode else (pens + pens_employer)
    total_monthly_income = netto_salary + reparations_cash + sfund_cash
    if include_pension:
        total_monthly_income += pens_total
    total_monthly_income2 = postprocess(total_monthly_income)
    print("---Other stats---")
    print(f"Pension: {round(pens_total)}")
    print(f"Reparations: {round(reparations_cash)}")
    print(f"Study fund: {round(sfund_cash)}")
    print(f"Total income: {round(total_monthly_income)}")
    if total_monthly_income != total_monthly_income2:
        print(f"Total income (post): {round(total_monthly_income2)}")
        total_monthly_income = total_monthly_income2

    # Part 3 (savings)
    if target is not None:
        monthly_gain = total_monthly_income - monthly_expense
        monthly_gain_rate = yearly_gain_rate ** (1 / 12)
        for i in itertools.count():
            if current_cash * monthly_gain_rate ** i + sum(monthly_gain * monthly_gain_rate ** j for j in range(i)) >= target:
                years = i / 12
                break
        print(f"{years:.1f} years to reach target of {round(target)} with {round(monthly_gain)} monthly saving")

    # Part 4 (employment cost)
    if not independent_mode and calculate_employment_cost:
        employer_pension = PENSION_EMPLOYER * social_salary
        employer_natins = tax_steps(
            salary_for_natins, EMPLOYER_NATIONAL_INSURANCE_STEPS)
        employment_cost = salary + ten_bis + goods + employer_natins + \
            employer_pension + reparations + employer_sfund
        print(f"Employment cost: {round(employment_cost)}")


if __name__ == "__main__":
    main()
