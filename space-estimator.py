# Script to give an estimate of the total number space for N digits
# Number of unqiue ID estimator
# N = number of digits in the ID
import random

N = 5
def estimate_uins(sample_size=1000000):
    # Define digits and even digits
    digits = list(range(N))
    even_digits = {0, 2, 4, 6, 8}
    odd_digits = set(digits) - even_digits

    # First digit cannot be '0' or '1'
    first_digits = list(range(2, 10))

    # Counters for total samples and valid UINs
    total_samples = 0
    valid_uins = 0

    for _ in range(sample_size):
        total_samples += 1
        seq = []

        # Generate the first digit
        first_digit = random.choice(first_digits)
        seq.append(first_digit)

        # Initialize variables for constraints
        consecutive_even_count = 1 if first_digit in even_digits else 0
        inc_seq_count = 1
        dec_seq_count = 1
        prev_digit = first_digit
        prev_prev_digit = None
        is_valid = True  # Flag to check if the sequence remains valid

        # Generate digits for positions 2 to N-1 (indexes 1 to 8)
        for position in range(1, N-1):
            # Possible digits excluding the previous digit to avoid adjacent repeats
            possible_digits = [d for d in digits if d != prev_digit]

            if not possible_digits:
                is_valid = False
                break  # No digits available, sequence invalid

            next_digit = random.choice(possible_digits)

            # Constraint: No three even adjacent digits
            if next_digit in even_digits:
                consecutive_even_count += 1
                if consecutive_even_count >= 3:
                    is_valid = False
                    break
            else:
                consecutive_even_count = 0

            # Constraint: No sequential numbers for 3 or more digits
            if prev_prev_digit is not None:
                if prev_prev_digit + 1 == prev_digit and prev_digit + 1 == next_digit:
                    is_valid = False  # Increasing sequence detected
                    break
                if prev_prev_digit - 1 == prev_digit and prev_digit - 1 == next_digit:
                    is_valid = False  # Decreasing sequence detected
                    break

            # Constraint: No repeated blocks of numbers for 2 or more digits
            # Check for immediate repetition of any block size from 2 up to half of the sequence so far
            repeated_block = False
            max_block_size = (position + 1) // 2
            for block_size in range(2, max_block_size + 1):
                if seq[-block_size:] == seq[-2*block_size:-block_size]:
                    repeated_block = True
                    break
            if repeated_block:
                is_valid = False
                break

            # Update sequence and variables for next iteration
            seq.append(next_digit)
            prev_prev_digit = prev_digit
            prev_digit = next_digit

        if not is_valid:
            continue  # Sequence invalid, skip to next sample

        # After generating the N-1 digit sequence, check the constraints involving the entire sequence

        # Constraint: First 5 digits should be different from last 5 digits
        first_five = seq[:5]
        last_five = seq[4:]
        if first_five == last_five:
            continue  # Invalid sequence

        # Constraint: First 5 digits should be different from the reverse of the last 5 digits
        if first_five == last_five[::-1]:
            continue  # Invalid sequence

        # Constraint: Should not be formed by repeating the first two digits five times
        if seq[:2] * 5 == seq:
            continue  # Invalid sequence

        # If all constraints are satisfied, increment the valid UINs counter
        valid_uins += 1

    # Estimate the total number of valid UINs
    total_possible_sequences = 8 * (9 ** (N-2))  # First digit has 8 options, next 8 digits have 9 options each
    estimated_total_valid_uins = (valid_uins / total_samples) * total_possible_sequences

    print(f"Total samples generated: {total_samples}")
    print(f"Valid UINs found: {valid_uins}")
    print(f"Estimated total valid UINs: {int(estimated_total_valid_uins)}")

# Call the function with a sample size (e.g., 1,000,000)
estimate_uins(sample_size=1000000)
