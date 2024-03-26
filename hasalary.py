#!/usr/bin/env python3
# coding: utf-8

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from dataclasses import dataclass, fields, replace
import itertools
import argparse
import os.path

# Income tax law, section 47a(a)
NATIONAL_INSURANCE_INDEPENDENT_WRITEOFF_RATE = 0.52


def tax_steps(s, steps):
    tax = 0
    last_step = 0
    for step, tax_rate in steps:
        tax += tax_rate * (min(step, s) - last_step)
        last_step = step
        if s <= step:
            break
    return tax


def income_tax(s, pts, consts):
    return tax_steps(s, consts["INCOME_TAX_STEPS"]) - (
        consts["INCOME_TAX_POINT_WORTH"] * pts
    )


def postprocess(x):
    return x


@dataclass
class Result:
    salary: float
    in_tax: float
    natins_tax: float
    healthins_tax: float
    pens: float
    pens_employer: float
    reparations: float
    sfund: float
    salary_for_income: float
    salary_for_natins: float
    salary_for_pens: float
    netto_salary: float


def impl(social_salary, non_social_salary, params, consts):
    salary = social_salary + non_social_salary
    if params["independent_mode"]:
        # Social paymens
        salary_for_pens = min(social_salary, consts["PENSION_INDEPENDENT_MAX_SALARY"])
        pens_a = consts["PENSION_INDEPENDENT_RATE_WRITEOFF"] * salary_for_pens
        pens_b = (
            consts["PENSION_INDEPENDENT_RATE_REIMBURSE"]
            + consts["PENSION_INDEPENDENT_RATE_REIMBURSE_ACA"]
        ) * salary_for_pens
        pens = pens_a + pens_b
        sfund = consts["STUDY_FUND_INDEPENDENT"] * min(
            social_salary, consts["STUDY_FUND_INDEPENDENT_MAX_SALARY"]
        )
        pens_employer = None
        reparations = None

        # National insurance
        salary_for_natins = salary - params["tax_worth_expenses"] - pens_a - sfund
        natins_tax = tax_steps(
            salary_for_natins, consts["INDEPENDENT_NATIONAL_INSURANCE_STEPS"]
        )
        healthins_tax = tax_steps(salary_for_natins, consts["HEALTH_INSURANCE_STEPS"])

        # Income tax
        salary_for_income = (
            salary
            - params["tax_worth_expenses"]
            - pens_a
            - sfund
            - natins_tax * NATIONAL_INSURANCE_INDEPENDENT_WRITEOFF_RATE
        )
        in_tax = income_tax(salary_for_income, params["tax_pts"], consts)
        in_tax -= consts["PENSION_REIMBURSE"] * pens_b
    else:
        tax_worth_features = params["ten_bis"] + params["goods"]

        # Social payments
        salary_for_pens = social_salary
        pens = params["PENSION_EMPLOYEE"] * salary_for_pens
        pens_employer = params["PENSION_EMPLOYER"] * salary_for_pens
        if pens_employer > consts["PENSION_EMPLOYER_TAX_EXEMPT_PAYMENTS_MAX"]:
            # Zkifat Tagmulim
            tax_worth_features += (
                pens_employer - consts["PENSION_EMPLOYER_TAX_EXEMPT_PAYMENTS_MAX"]
            )
        reparations = params["PENSION_REPARATIONS"] * salary_for_pens
        if reparations > consts["PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX"]:
            # Zkifat Pitzuiim
            tax_worth_features += (
                reparations - consts["PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX"]
            )
        if (
            social_salary > consts["STUDY_FUND_TAX_EXEMPT_MAX"]
            and params["full_study_fund"]
        ):
            # Zkifat Hishtalmut
            tax_worth_features += (
                social_salary - consts["STUDY_FUND_TAX_EXEMPT_MAX"]
            ) * consts["STUDY_FUND_EMPLOYER"]
            sfund = consts["STUDY_FUND_EMPLOYEE"] * social_salary
        else:
            sfund = consts["STUDY_FUND_EMPLOYEE"] * min(
                social_salary, consts["STUDY_FUND_TAX_EXEMPT_MAX"]
            )

        # National Insurance
        salary_for_natins = salary + tax_worth_features
        natins_tax = tax_steps(salary_for_natins, consts["NATIONAL_INSURANCE_STEPS"])
        healthins_tax = tax_steps(salary_for_natins, consts["HEALTH_INSURANCE_STEPS"])

        # Income Tax
        salary_for_income = salary + tax_worth_features
        in_tax = income_tax(salary_for_income, params["tax_pts"], consts)
        in_tax -= consts["PENSION_REIMBURSE"] * min(
            pens, consts["PENSION_REIMBURSE_PAYMENTS_MAX"]
        )

    netto_salary = salary - in_tax - natins_tax - healthins_tax - pens - sfund
    return Result(
        salary,
        in_tax,
        natins_tax,
        healthins_tax,
        pens,
        pens_employer,
        reparations,
        sfund,
        salary_for_income,
        salary_for_natins,
        salary_for_pens,
        netto_salary,
    )


def result_filter(params, result: Result) -> Result:
    for field in fields(result):
        value = getattr(result, field.name)
        if value is None:
            continue
        if params["annual_numbers"]:
            value *= 12
        result = replace(result, **{field.name: round(value)})

    if result.in_tax < 0:
        print(
            f"WARNING: got negative income tax, {round(-result.in_tax)} in tax benefits is wasted"
        )
        result.in_tax = 0

    return result


def params_filter(params):
    if not params["annual_numbers"]:
        return params

    params = dict(params)
    params.update(
        (key, params[key] / 12)
        for key in [
            "base_salary",
            "travel_allowance",
            "bonuses",
            "ten_bis",
            "goods",
            "tax_worth_expenses",
        ]
        if key in params
    )
    return params


def main():
    # Loading config
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=str, help="config to be used")
    args = parser.parse_args()
    with open(f"{args.config}", "r", encoding="utf-8") as f:
        params = {}
        exec(f.read(), params)

    try:
        with open(
            os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                "constants",
                f"{params['TAX_YEAR']}.py",
            ),
            "r",
            encoding="utf-8",
        ) as f:
            consts = {}
            exec(f.read(), consts)
    except FileNotFoundError:
        print(f"Tax calculations for {params['TAX_YEAR']} not supported")
        return

    params = params_filter(params)

    if params["independent_mode"]:
        social_salary = params["base_salary"] - params["tax_worth_expenses"]
        non_social_salary = 0
    else:
        social_salary = params["base_salary"] * params["percentage"]
        non_social_salary = params["travel_allowance"] + params["bonuses"]

    result = impl(social_salary, non_social_salary, params, consts)

    rate = [
        rate
        for ceiling, rate in consts["INCOME_TAX_STEPS"]
        if result.salary_for_income < ceiling
    ][0]
    result2 = impl(social_salary + 1, non_social_salary, params, consts)
    effrate = result2.in_tax - result.in_tax
    effrate_text = (
        f"; effective marginal rate {effrate:.2f}" if (rate - effrate) >= 0.01 else ""
    )

    result_pretty = result_filter(params, result)

    # Part 1 (paycheck)
    print("---Paycheck details---")
    print(
        f"Income tax: {result_pretty.in_tax} from a salary of {result_pretty.salary_for_income} (marginal rate {rate}{effrate_text})"
    )
    print(
        f"National Insurance: {result_pretty.natins_tax} from a salary of {result_pretty.salary_for_natins}"
    )
    print(
        f"Health Insurance: {result_pretty.healthins_tax} from a salary of {result_pretty.salary_for_natins}"
    )
    print(
        f"Pension: {result_pretty.pens} from a salary of {result_pretty.salary_for_pens}"
    )
    print(f"Study Fund: {result_pretty.sfund}")
    print(f"Salary (Net): {result_pretty.netto_salary}")
    print("-------------------------------------")

    # Part 2 (total income)
    if params["independent_mode"]:
        reparations_cash = 0
        employer_sfund = 0
    else:
        reparations_cash = min(
            result.reparations, consts["REPARATIONS_PULL_TAX_EXEMPT_MAX"]
        )
        if result.reparations > consts["PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX"]:
            reparations_cash += (
                result.reparations
                - consts["PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX"]
            )
        if params["include_pension"]:
            reparations_cash = result.reparations
        elif (
            params["monthly_reparations_pull"]
            and result.reparations > consts["REPARATIONS_PULL_TAX_EXEMPT_MAX"]
        ):
            taxed_reparations = result.reparations - reparations_cash
            tax_rate = (
                income_tax(
                    params["monthly_reparations_pull"], params["tax_pts"], consts
                )
                / params["monthly_reparations_pull"]
            )
            reparations_cash += taxed_reparations * (1 - tax_rate)
        employer_sfund = consts["STUDY_FUND_EMPLOYER"] * (
            social_salary
            if params["full_study_fund"]
            else min(social_salary, consts["STUDY_FUND_TAX_EXEMPT_MAX"])
        )

    sfund_cash = result.sfund + employer_sfund
    pens_total = (
        result.pens
        if params["independent_mode"]
        else (result.pens + result.pens_employer)
    )
    total_monthly_income = result.netto_salary + reparations_cash + sfund_cash
    if params["include_pension"]:
        total_monthly_income += pens_total
    total_monthly_income2 = postprocess(total_monthly_income)

    if params["annual_numbers"]:
        pens_total *= 12
        reparations_cash *= 12
        sfund_cash *= 12
    print("---Other stats---")
    print(f"Pension: {round(pens_total)}")
    print(f"Reparations: {round(reparations_cash)}")
    print(f"Study fund: {round(sfund_cash)}")
    print(f"Total monthly income: {round(total_monthly_income)}")
    print(f"Total annual income: {round(total_monthly_income * 12)}")
    if total_monthly_income != total_monthly_income2:
        print(f"Total monthly income (post): {round(total_monthly_income2)}")
        print(f"Total annual income (post): {round(total_monthly_income2 * 12)}")
        total_monthly_income = total_monthly_income2

    # Part 3 (savings)
    if params["target"] is not None:
        monthly_gain = total_monthly_income - params["monthly_expense"]
        monthly_gain_rate = params["yearly_gain_rate"] ** (1 / 12)
        for i in itertools.count():
            if (
                params["current_cash"] * monthly_gain_rate**i
                + sum(monthly_gain * monthly_gain_rate**j for j in range(i))
                >= params["target"]
            ):
                years = i / 12
                break
        print(
            f"{years:.1f} years to reach target of {round(params['target'])} with {round(monthly_gain)} monthly saving"
        )

    # Part 4 (employment cost)
    if not params["independent_mode"] and params["calculate_employment_cost"]:
        employer_pension = params["PENSION_EMPLOYER"] * social_salary
        employer_natins = tax_steps(
            result.salary_for_natins, consts["EMPLOYER_NATIONAL_INSURANCE_STEPS"]
        )
        employment_cost = (
            result.salary
            + params["ten_bis"]
            + params["goods"]
            + employer_natins
            + employer_pension
            + result.reparations
            + employer_sfund
        )
        print(f"Employment cost: {round(employment_cost)}")


if __name__ == "__main__":
    main()
