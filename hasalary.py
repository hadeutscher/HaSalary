#!/usr/bin/env python3
# coding: utf-8

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from dataclasses import dataclass, fields, replace
import itertools
import argparse
import math
import os.path
import logging

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


def natins_independent(y, consts):
    m, t1 = consts["INDEPENDENT_NATIONAL_INSURANCE_STEPS"][0]
    _, t2 = consts["INDEPENDENT_NATIONAL_INSURANCE_STEPS"][1]
    z = NATIONAL_INSURANCE_INDEPENDENT_WRITEOFF_RATE

    # Voodoo magic
    # https://www.btl.gov.il/Insurance/National%20Insurance/type_list/Self_Employed/Pages/hishov.dmey.bituach.aspx
    x = y - m * z * t1
    if x <= m:
        return x
    else:
        return (y + m * z * (t2 - t1)) / (1 + z * t2)


def postprocess(x):
    return x


@dataclass
class Details:
    salary: float
    in_tax: float
    natins_tax: float
    healthins_tax: float
    pens: float
    pens_employer: float
    reparations: float
    sfund: float
    sfund_employer: float
    salary_for_income: float
    salary_for_natins: float
    salary_for_pens: float
    netto_salary: float
    natins_employer: float


@dataclass
class Result:
    details: Details
    tax_values: dict[str, float]


def impl(social_salary, non_social_salary, params, consts) -> Result:
    tax = dict()
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
        sfund_employer = None
        reparations = None

        tax_worth_expenses = params["tax_worth_expenses"]

        # National insurance
        salary_for_natins = natins_independent(
            salary - tax_worth_expenses - pens_a - sfund, consts
        )
        natins_tax = tax_steps(
            salary_for_natins, consts["INDEPENDENT_NATIONAL_INSURANCE_STEPS"]
        )
        natins_employer = None
        healthins_tax = tax_steps(salary_for_natins, consts["HEALTH_INSURANCE_STEPS"])
        natins_writeoff = natins_tax * NATIONAL_INSURANCE_INDEPENDENT_WRITEOFF_RATE
        if params.get("experimental_delay_natins_payment", False):
            natins_writeoff = 0

        # Income tax
        tax["deduction tax_worth_expenses"] = tax_worth_expenses
        tax["deduction pens_a"] = pens_a
        tax["deduction sfund"] = sfund
        tax["deduction natins_writeoff"] = natins_writeoff
        salary_for_income = (
            salary - tax_worth_expenses - pens_a - sfund - natins_writeoff
        )
        prev_worth = params.get("experimental_injected_previous_tax_worth")
        if prev_worth is not None:
            tax["worth prev_worth"] = prev_worth
            salary_for_income += prev_worth
        in_tax = income_tax(salary_for_income, params["tax_pts"], consts)
        pens_b_re = consts["PENSION_REIMBURSE"] * pens_b
        tax["reimburse pens_b_re"] = pens_b_re
        in_tax -= pens_b_re

        prev_45a = params.get("experimental_injected_45a_value")
        if prev_45a is not None:
            pension_re = consts["PENSION_REIMBURSE"] * min(
                prev_45a, consts["PENSION_REIMBURSE_PAYMENTS_MAX"]
            )
            tax["reimburse prev_45a"] = pension_re
            in_tax -= pension_re

    else:
        tax_worth_features = params["ten_bis"] + params["goods"]
        tax["worth tax_worth_features"] = tax_worth_features

        # Social payments
        salary_for_pens = social_salary
        pens = params["PENSION_EMPLOYEE"] * salary_for_pens
        pens_employer = params["PENSION_EMPLOYER"] * salary_for_pens
        if pens_employer > consts["PENSION_EMPLOYER_TAX_EXEMPT_PAYMENTS_MAX"]:
            # Zkifat Tagmulim
            pens_employer_taxed = (
                pens_employer - consts["PENSION_EMPLOYER_TAX_EXEMPT_PAYMENTS_MAX"]
            )
            tax["worth pens_employer_taxed"] = pens_employer_taxed
            tax_worth_features += pens_employer_taxed
        reparations = params["PENSION_REPARATIONS"] * salary_for_pens
        if reparations > consts["PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX"]:
            # Zkifat Pitzuiim
            reparations_taxed = (
                reparations - consts["PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX"]
            )
            tax["worth reparations_taxed"] = reparations_taxed
            tax_worth_features += reparations_taxed
        if (
            social_salary > consts["STUDY_FUND_TAX_EXEMPT_MAX"]
            and params["full_study_fund"]
        ):
            # Zkifat Hishtalmut
            sfund_taxed = (
                social_salary - consts["STUDY_FUND_TAX_EXEMPT_MAX"]
            ) * consts["STUDY_FUND_EMPLOYER"]
            tax_worth_features += sfund_taxed
            tax["worth sfund_taxed"] = sfund_taxed
            sfund_salary = social_salary
        else:
            sfund_salary = min(social_salary, consts["STUDY_FUND_TAX_EXEMPT_MAX"])

        sfund = consts["STUDY_FUND_EMPLOYEE"] * sfund_salary
        sfund_employer = consts["STUDY_FUND_EMPLOYER"] * sfund_salary

        # National Insurance
        salary_for_natins = salary + tax_worth_features
        natins_tax = tax_steps(salary_for_natins, consts["NATIONAL_INSURANCE_STEPS"])
        healthins_tax = tax_steps(salary_for_natins, consts["HEALTH_INSURANCE_STEPS"])
        natins_employer = tax_steps(
            salary_for_natins, consts["EMPLOYER_NATIONAL_INSURANCE_STEPS"]
        )

        # Income Tax
        salary_for_income = salary + tax_worth_features
        in_tax = income_tax(salary_for_income, params["tax_pts"], consts)
        pension_re = consts["PENSION_REIMBURSE"] * min(
            pens, consts["PENSION_REIMBURSE_PAYMENTS_MAX"]
        )
        tax["reimburse pension_re"] = pension_re
        in_tax -= pension_re

    netto_salary = salary - in_tax - natins_tax - healthins_tax - pens - sfund
    prev_income = params.get("experimental_injected_net_income")
    if prev_income is not None:
        netto_salary += prev_income
    details = Details(
        salary,
        in_tax,
        natins_tax,
        healthins_tax,
        pens,
        pens_employer,
        reparations,
        sfund,
        sfund_employer,
        salary_for_income,
        salary_for_natins,
        salary_for_pens,
        netto_salary,
        natins_employer,
    )
    return Result(details, tax)


def result_filter(params, result: Result) -> Result:
    details = result.details
    for field in fields(details):
        value = getattr(details, field.name)
        if value is None:
            continue
        if params["annual_numbers"]:
            value *= 12
        details = replace(details, **{field.name: round(value)})

    if details.in_tax < 0:
        logging.getLogger().warn(
            f"got negative income tax, {round(-details.in_tax)} in tax benefits is wasted"
        )
        details.in_tax = 0

    tax_values = dict(result.tax_values)
    if params["annual_numbers"]:
        tax_values = {k: v * 12 for k, v in tax_values.items()}
    return Result(details, tax_values)


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


@dataclass
class RatesResult:
    income_rate: float
    natins_rate: float
    healthins_rate: float
    total_rate: float


def calculate_effective_marginal_rate(
    base: float, result1: Result, result2: Result
) -> RatesResult:
    if (
        result1.details.pens_employer is not None
        and result1.details.sfund_employer is not None
        and result1.details.reparations is not None
        and result2.details.pens_employer is not None
        and result2.details.sfund_employer is not None
        and result2.details.reparations is not None
    ):
        assert result2.details.pens_employer >= result1.details.pens_employer
        assert result2.details.sfund_employer >= result1.details.sfund_employer
        assert result2.details.reparations >= result1.details.reparations
        base += (
            (result2.details.pens_employer - result1.details.pens_employer)
            + (result2.details.sfund_employer - result1.details.sfund_employer)
            + (result2.details.reparations - result1.details.reparations)
        )
    if result1.details.in_tax <= 0 and result1.details.in_tax <= 0:
        income_rate = 0
    else:
        income_rate = (result2.details.in_tax - result1.details.in_tax) / base
    natins_rate = (result2.details.natins_tax - result1.details.natins_tax) / base
    healthins_rate = (
        result2.details.healthins_tax - result1.details.healthins_tax
    ) / base
    total_rate = income_rate + natins_rate + healthins_rate
    return RatesResult(income_rate, natins_rate, healthins_rate, total_rate)


def main():
    # Loading config
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=str, help="config to be used")
    parser.add_argument("-v", "--verbose", action="store_true", help="extra logs")
    parser.add_argument("-s", "--steps", action="store_true", help="extra logs")
    args = parser.parse_args()

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)
    log = logging.getLogger()

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
        log.error(f"Tax calculations for {params['TAX_YEAR']} not supported")
        return

    params = params_filter(params)

    if args.steps:
        print("---Tax steps analysis---")
        last_step = [
            ceiling for ceiling, _ in consts["INCOME_TAX_STEPS"] if ceiling < math.inf
        ][-1]
        last_rate = None
        last_rate_floor = 0
        params_clean = dict(params)
        params_clean.update(tax_worth_expenses=0, ten_bis=0, goods=0)
        output_filter = (
            (lambda x: round(x * 12))
            if params["annual_numbers"]
            else (lambda x: round(x))
        )
        for income in range(int(last_step) * 12 * 2):
            income /= 12
            result1 = impl(income, 0, params_clean, consts)
            result2 = impl(income + 1 / 12, 0, params_clean, consts)
            effrate = calculate_effective_marginal_rate(1 / 12, result1, result2)
            if args.verbose:
                for result in (result1, result2):
                    log_tax = logging.getLogger("taxes")
                    result_pretty = result_filter(params, result)
                    for k, v in result_pretty.tax_values.items():
                        log_tax.debug(f"{k}={v}")

            if last_rate is None:
                last_rate = effrate
                last_rate_floor = income
            elif (
                abs(effrate.total_rate - last_rate.total_rate) >= 0.005
                and income - last_rate_floor > 10
            ):
                print(
                    f"{output_filter(last_rate_floor)} - {output_filter(income)}: {last_rate.total_rate:.2f} ({last_rate.income_rate:.2f}, {last_rate.natins_rate:.2f}, {last_rate.healthins_rate:.2f})"
                )
                last_rate_floor = income
            last_rate = effrate
        print(
            f"{output_filter(last_rate_floor)} - infinity: {last_rate.total_rate:.2f} ({last_rate.income_rate:.2f}, {last_rate.natins_rate:.2f}, {last_rate.healthins_rate:.2f})"
        )
        return

    if params["independent_mode"]:
        social_salary = params["base_salary"] - params["tax_worth_expenses"]
        non_social_salary = params["tax_worth_expenses"]
    else:
        social_salary = params["base_salary"] * params["percentage"]
        non_social_salary = params["travel_allowance"] + params["bonuses"]

    result = impl(social_salary, non_social_salary, params, consts)

    rate = [
        rate
        for ceiling, rate in consts["INCOME_TAX_STEPS"]
        if result.details.salary_for_income < ceiling
    ][0]
    result2 = impl(social_salary + 1, non_social_salary, params, consts)
    effrate = calculate_effective_marginal_rate(1, result, result2)
    effrate_text = (
        f"; effective marginal rate {effrate.income_rate:.2f}"
        if abs(rate - effrate.income_rate) >= 0.01
        else ""
    )

    result_pretty = result_filter(params, result)
    log_tax = logging.getLogger("taxes")
    for k, v in result_pretty.tax_values.items():
        log_tax.debug(f"{k}={v}")
    details_pretty = result_pretty.details

    # Part 1 (paycheck)
    print("---Paycheck details---")
    print(
        f"Income tax: {details_pretty.in_tax} from a salary of {details_pretty.salary_for_income} (marginal rate {rate}{effrate_text})"
    )
    print(
        f"National Insurance: {details_pretty.natins_tax} from a salary of {details_pretty.salary_for_natins}"
    )
    print(
        f"Health Insurance: {details_pretty.healthins_tax} from a salary of {details_pretty.salary_for_natins}"
    )
    print(
        f"Pension: {details_pretty.pens} from a salary of {details_pretty.salary_for_pens}"
    )
    print(f"Study Fund: {details_pretty.sfund}")
    print(f"Salary (Net): {details_pretty.netto_salary}")
    print("-------------------------------------")

    # Part 2 (total income)
    details = result.details
    if params["independent_mode"]:
        reparations_cash = 0
    else:
        reparations_cash = min(
            details.reparations, consts["REPARATIONS_PULL_TAX_EXEMPT_MAX"]
        )
        if details.reparations > consts["PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX"]:
            reparations_cash += (
                details.reparations
                - consts["PENSION_REPARATIONS_TAX_EXEMPT_PAYMENTS_MAX"]
            )
        if params["include_pension"]:
            reparations_cash = details.reparations
        elif (
            params["monthly_reparations_pull"]
            and details.reparations > consts["REPARATIONS_PULL_TAX_EXEMPT_MAX"]
        ):
            taxed_reparations = details.reparations - reparations_cash
            tax_rate = (
                income_tax(
                    params["monthly_reparations_pull"], params["tax_pts"], consts
                )
                / params["monthly_reparations_pull"]
            )
            reparations_cash += taxed_reparations * (1 - tax_rate)

    sfund_cash = (
        details.sfund
        if params["independent_mode"]
        else details.sfund + details.sfund_employer
    )
    pens_total = (
        details.pens
        if params["independent_mode"]
        else (details.pens + details.pens_employer)
    )
    total_monthly_income = details.netto_salary + reparations_cash + sfund_cash
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
        employment_cost = (
            details.salary
            + params["ten_bis"]
            + params["goods"]
            + details.natins_employer
            + details.pens_employer
            + details.reparations
            + details.sfund_employer
        )
        print(f"Employment cost: {round(employment_cost)}")


if __name__ == "__main__":
    main()
